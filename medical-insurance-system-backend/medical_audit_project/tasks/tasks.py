import logging
import json
import os
import random
import re
from datetime import datetime
from celery import shared_task
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.db import transaction, close_old_connections
from django.conf import settings
from engine.engine import RuleEngine # 导入我们改造后的引擎
from django.conf import settings
from cases.models import Case # 导入新的 Case 模型

from data_adapter.medical_api import MedicalAPI
from data_adapter.source_db import get_source_db_config

# 导入所有需要的模型
from .models import Task
from results.models import Result, Highlight
from rules.models import Rule
from engine.engine import RuleEngine
from engine.over_standard_v2 import check_over_standard
from engine.duplicate_billing import detect_duplicate_charges 
logger = logging.getLogger(__name__)


def _normalize_discharge_date(patient_json):
    """返回可写入 Result.discharge_date 的标准时间；无法识别时返回空值。"""
    if not isinstance(patient_json, dict):
        return None

    discharge_record = patient_json.get('出院记录') or {}
    basic_info = patient_json.get('基本信息') or {}
    raw_value = (
        discharge_record.get('出院日期')
        if isinstance(discharge_record, dict) else None
    ) or (
        basic_info.get('出院日期')
        if isinstance(basic_info, dict) else None
    )
    if not raw_value:
        return None

    if isinstance(raw_value, datetime):
        parsed = raw_value
    else:
        text = str(raw_value).strip()
        if not text or text.lower() in {'xxx', 'none', 'null', '文本中未提及该内容'}:
            return None

        parsed = parse_datetime(text)
        if parsed is None:
            parsed_date = parse_date(text)
            if parsed_date is not None:
                parsed = datetime.combine(parsed_date, datetime.min.time())

        if parsed is None:
            chinese_match = re.fullmatch(
                r'(\d{4})年(\d{1,2})月(\d{1,2})日'
                r'(?:\s*(\d{1,2})时(?:(\d{1,2})分)?(?:(\d{1,2})秒)?)?',
                text,
            )
            if chinese_match:
                year, month, day, hour, minute, second = chinese_match.groups()
                try:
                    parsed = datetime(
                        int(year), int(month), int(day),
                        int(hour or 0), int(minute or 0), int(second or 0),
                    )
                except ValueError:
                    parsed = None

        if parsed is None:
            logger.warning('病历出院日期格式无法识别，结果将不写入出院日期：%r', raw_value)
            return None

    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _fallback_task_self_reflection(requested_count, processed_count, rule_count, total_violation_count):
    """模型输出不合规或不可用时，按任务统计生成固定格式的中文自检结果。"""
    needs_attention = requested_count != processed_count or rule_count <= 0
    conclusion = '提示关注。' if needs_attention else '通过。'
    verification = (
        f'计划处理{requested_count}例，实际处理{processed_count}例，'
        f'关联规则{rule_count}条，已固化违规{total_violation_count}条。'
    )
    suggestion = '请人工确认任务配置与执行结果。' if needs_attention else '无需额外处理。'
    return f'结论：{conclusion}\n核验：{verification}\n建议：{suggestion}'


def _normalize_task_self_reflection(raw_text, requested_count, processed_count, rule_count, total_violation_count):
    """只接受三行中文自检结论，屏蔽模型可能返回的推理过程或英文内容。"""
    fallback = _fallback_task_self_reflection(
        requested_count, processed_count, rule_count, total_violation_count
    )
    if not raw_text:
        return fallback

    labels = {}
    for raw_line in str(raw_text).replace('\r', '').split('\n'):
        line = raw_line.strip().replace('**', '')
        matched = re.match(r'^(?:[-*]\s*)?(结论|核验|建议)\s*[：:]\s*(.+)$', line)
        if not matched:
            continue
        label, value = matched.groups()
        value = value.strip()
        # 跳过模型复述提示词时常见的“通过 或 提示关注”“说明已核验”等说明性行。
        if not value or len(value) > 180 or re.search(r'[A-Za-z]', value):
            continue
        if label == '结论' and value not in ('通过', '通过。', '提示关注', '提示关注。'):
            continue
        labels[label] = value

    if set(labels) != {'结论', '核验', '建议'}:
        return fallback

    result = f"结论：{labels['结论']}\n核验：{labels['核验']}\n建议：{labels['建议']}"
    if len(result) > 300 or re.search(r'[A-Za-z]', result):
        return fallback
    return result


def build_task_self_reflection(task, processed_count, total_violation_count, rule_count):
    """生成任务级轻量计算自检文本；仅保存三行中文结果，不保存模型推理过程。"""
    requested_count = len(task.hospitalization_ids or [])
    prompt = f"""你是医保审查任务的计算自检助手。仅依据以下任务统计进行辅助核验，不得重算病历、不得判断新增违规、不得修改既有结论。

任务ID：{task.id}
审查方案：{', '.join(task.selected_schemas or []) or '未选择'}
关联规则数：{rule_count}
计划处理病例数：{requested_count}
实际处理病例数：{processed_count}
已固化违规数：{total_violation_count}

【严格输出限制】
只输出中文最终结果，且必须恰好三行。不得输出英文、分析、推理过程、思考过程、草稿、标题、Markdown 或任何额外文字。
结论：通过。或 提示关注。
核验：写明计划与实际病例数、关联规则数的核验结果。
建议：无异常写“无需额外处理。”；病例数不一致或规则数为零时写“请人工确认任务配置与执行结果。”
"""
    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=getattr(settings, 'RULE_IMPORT_LLM_API_KEY', '') or 'EMPTY',
            base_url=getattr(settings, 'RULE_IMPORT_LLM_BASE_URL', ''),
            timeout=20,
        )
        response = client.chat.completions.create(
            model=getattr(settings, 'RULE_IMPORT_LLM_MODEL_EXTRACT', 'qwen'),
            messages=[
                {
                    'role': 'system',
                    'content': '你只输出最终三行中文结论，绝不输出分析、推理、思考过程或英文。',
                },
                {'role': 'user', 'content': prompt},
            ],
            temperature=0,
            max_tokens=180,
        )
        reflection = (response.choices[0].message.content or '').strip()
        return _normalize_task_self_reflection(
            reflection, requested_count, processed_count, rule_count, total_violation_count
        )
    except Exception as exc:  # noqa: BLE001 - 自检是辅助能力，必须隔离模型故障
        logger.warning('任务 %s 计算自检未生成: %s', task.id, exc)
        return _fallback_task_self_reflection(
            requested_count, processed_count, rule_count, total_violation_count
        )


def get_patient_data(hospitalization_id: str, mdc_org_cd: str = None):
    """
    数据获取辅助函数，增加了缓存逻辑，并通过“猴子补丁”注入配置。
    """
    # --- 1. 尝试从缓存读取 ---
    cache_key = f"{mdc_org_cd}:{hospitalization_id}" if mdc_org_cd else hospitalization_id
    try:
        case = Case.objects.get(pk=cache_key)
        logger.info(f"成功从缓存表 (cases_case) 中命中病历: {hospitalization_id}")
        return case.json_content
    except Case.DoesNotExist:
        logger.info(f"缓存未命中，需要从数据源获取病历: {hospitalization_id}")
        pass

    # --- 2. 从数据源获取 ---
    patient_json = None
    is_local_dev = getattr(settings, 'LOCAL_DEV_MODE', False)

    try:
        if is_local_dev:
            # 本地开发模式：从本地文件读取
            logger.info(f"本地模式: 尝试从文件加载 {hospitalization_id}.json")
            base_dir = settings.BASE_DIR
            file_path = os.path.join(base_dir, "mock_patient_data", f"{hospitalization_id}.json")
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    patient_json = json.load(f)
                    logger.info(f"成功加载模拟文件: {hospitalization_id}.json")
            else:
                raise FileNotFoundError(f"本地模拟数据文件 {hospitalization_id}.json 不存在。")
        
        else:
            logger.info(f"生产模式: 从统一源库配置获取住院号 {hospitalization_id} 的病历")
            medical_api = MedicalAPI(db_config=get_source_db_config())
            result = medical_api.get_patient_final_json_data(hospitalization_id, mdc_org_cd)

            if result.get('success'):
                patient_json = result['json_data']
            else:
                raise ConnectionError(f"获取数据失败: {result.get('error')}")

    except Exception as e:
        logger.error(f"从数据源获取 {hospitalization_id} 失败: {e}")
        raise e
    # --- 3. 获取到新数据后，更新或创建缓存 ---
    if patient_json:
        try:
            Case.objects.update_or_create(
                hospitalization_id=cache_key,
                defaults={'json_content': patient_json}
            )
            logger.info(f"已将病历 {hospitalization_id} 写入/更新到缓存表 (cases_case)。")
        except Exception as cache_error:
            logger.error(f"写入病历缓存 {hospitalization_id} 失败: {cache_error}")
    
    return patient_json
@shared_task
def run_audit_task(task_id):
    close_old_connections()
    task = None
    try:
        # --- 【第一层诊断】: 看看从数据库里拿到的 task 对象是什么 ---
        task = Task.objects.prefetch_related('rules').get(id=task_id)
        
        logger.info("="*50)
        logger.info(f"【任务内部诊断】任务 ID: {task.id}")
        logger.info(f"【任务内部诊断】任务名称: {task.name}")
        logger.info(f"【任务内部诊断】选择的方案 (selected_schemas): {task.selected_schemas}")
        logger.info(f"【任务内部诊断】selected_schemas 的类型: {type(task.selected_schemas)}")

        all_rules_for_task_diag = list(task.rules.all())
        rule_ids_for_task = [r.id for r in all_rules_for_task_diag]
        logger.info(f"【任务内部诊断】关联的规则 ID 列表: {rule_ids_for_task}")
        logger.info(f"【任务内部诊断】关联的规则数量: {len(all_rules_for_task_diag)}")
        logger.info("="*50)

        # --- 1. 任务初始化 ---
        # 注意：这里的 task 变量会覆盖上面的 task，但因为 id 相同，所以数据是一致的
        with transaction.atomic():
            task = Task.objects.select_for_update().get(id=task_id)
            if task.status == 'running':
                logger.warning(f"任务 {task_id} 已在运行，本次调度跳过。")
                return
            task.status = 'running'
            task.started_at = timezone.now()
            task.completed_at = None
            task.summary = "任务开始执行..."
            task.self_reflection = ''
            task.save()

        logger.info(f"开始执行任务 ID: {task.id}, 名称: {task.name}")
        task.results.all().delete()
        
        all_rules_for_task = list(task.rules.all())
        processed_count = 0
        total_violation_count = 0
        mdc_org_cd = (task.mdc_org_cd or getattr(settings, 'SOURCE_MDC_ORG_CD', '') or '').strip()

        # --- 2. 循环处理每个住院号 ---
        for hos_id in task.hospitalization_ids:
            try:
                logger.info(f"--- 正在处理住院号: {hos_id} ---")
                patient_json = get_patient_data(hos_id, mdc_org_cd)
                if not patient_json or patient_json.get('error'):
                    logger.warning(f"获取住院号 {hos_id} 的病历JSON失败或为空，跳过处理。")
                    continue

                # --- 【修正后的逻辑结构】 ---

                # --- 模块一：独立判断和执行"超限定用药" ---
                if '超限定用药' in task.selected_schemas:
                    # [V2] 使用新版逻辑引擎 (L1/L2/Interface)
                    # 动态导入以防止 Celery 加载时序导致的 NameError
                    from engine.over_standard_v2 import check_indication_rule
                    
                    logger.info(f"为 {hos_id} 开始执行'超限定用药'审核 (V2: Indication Check)...")
                    # 【修正】传入 task.rules.all() 作为 target_rules
                    all_rules_for_task = list(task.rules.all())
                    # 增加日志确认
                    logger.info(f"Task {task.id} passing {len(all_rules_for_task)} rules to engine.")

                    drug_audit_results = check_indication_rule(patient_json, target_rules=all_rules_for_task)
                    
                    # 保存"超限定用药"的结果
                    for res in drug_audit_results:
                        # 新格式：passed=False 表示违规，或兼容旧格式 violation=True
                        is_violation = not res.get('passed', True) or res.get('violation', False)
                        if is_violation:
                            try:
                                # 对于新引擎，规则对象可能是虚拟的，不一定存在于数据库
                                # 尝试获取或创建一个虚拟规则对象
                                rule_info = res.get('rule', {})
                                rule_id = res.get('ruleId') or rule_info.get('rule_id') or 'UNKNOWN_RULE'
                                
                                rule_obj, _ = Rule.objects.get_or_create(
                                    rule_id=rule_id,
                                    defaults={
                                        'drug_name': rule_info.get('drug_name', '未命名规则'),
                                        'description': rule_info.get('description', '自动生成规则'),
                                        'type': '超限定用药'
                                    }
                                )
                                
                                with transaction.atomic():
                                    cleaned_discharge_date = _normalize_discharge_date(patient_json)
                                    
                                    # 新格式使用 reason，旧格式使用 problem
                                    reason = res.get('reason', res.get('problem', 'N/A'))
                                    
                                    db_result = Result.objects.create(
                                        task=task,
                                        rule=rule_obj,
                                        hospitalization_id=hos_id,
                                        reason=str(reason),
                                        violation_item=json.dumps(res.get('item', {}), ensure_ascii=False, default=str),
                                        discharge_date=cleaned_discharge_date
                                    )
                                    
                                    highlights_data = res.get('highlights', [])
                                    if highlights_data:
                                        logger.info(f"为违规结果 {db_result.id} 找到 {len(highlights_data)} 条高亮证据，准备写入数据库。")
                                        for hl in highlights_data:
                                            Highlight.objects.create(
                                                result=db_result,
                                                field_path=hl.get('field_path', 'N/A'),
                                                highlighted_text=str(hl.get('highlighted_text', ''))
                                            )
                                total_violation_count += 1
                            except Exception as db_error:
                                logger.error(f"保存'超限定用药'违规结果时出错: {db_error}", exc_info=True)
                
                # --- 模块二：独立判断和执行“超标准收费” ---
                if '超标准收费' in task.selected_schemas:
                    from engine.over_standard_v2 import execute_db_rules
                    logger.info(f"为 {hos_id} 开始执行'超标准收费'审核 (V2: DB Driven)...")
                    # 使用通用的 execute_db_rules
                    # 【修正】传入 task.rules.all() 作为 target_rules
                    all_rules_for_task = list(task.rules.all())
                    charge_audit_results = execute_db_rules(patient_json, rule_type='超标准收费', target_rules=all_rules_for_task)
                    
                    # 保存“超标准收费”的结果
                    for res in charge_audit_results:
                        is_violation = not res.get('passed', True) or res.get('violation', False)
                        if is_violation:
                            try:
                                rule_info = res.get('rule', {})
                                rule_id = res.get('ruleId') or rule_info.get('rule_id') or 'UNKNOWN_RULE'
                                
                                rule_obj, _ = Rule.objects.get_or_create(
                                    rule_id=rule_id,
                                    defaults={
                                        'drug_name': rule_info.get('drug_name', '通用规则'),
                                        'description': rule_info.get('description', ''),
                                        'type': rule_info.get('type', '超标准收费')
                                    }
                                )
                                with transaction.atomic():
                                    cleaned_discharge_date = _normalize_discharge_date(patient_json)

                                    reason = res.get('reason', res.get('problem', 'N/A'))

                                    db_result = Result.objects.create(
                                        task=task,
                                        rule=rule_obj,
                                        hospitalization_id=hos_id,
                                        reason=str(reason),
                                        violation_item=json.dumps(res.get('item', {}), ensure_ascii=False, default=str),
                                        discharge_date=cleaned_discharge_date
                                    )
                                    
                                    highlights_data = res.get('highlights', [])
                                    if highlights_data:
                                        logger.info(f"[OverStandard] 为违规结果 {db_result.id} 找到 {len(highlights_data)} 条高亮证据，准备写入数据库。")
                                        for hl in highlights_data:
                                            Highlight.objects.create(
                                                result=db_result,
                                                field_path=hl.get('field_path', 'N/A'),
                                                highlighted_text=str(hl.get('highlighted_text', ''))
                                            )
                                    total_violation_count += 1
                            # 【修正点 1】修复 Pylance 报错
                            except Exception as db_error:
                                logger.error(f"保存'超标准收费'违规结果时出错: {db_error}", exc_info=True)
                
                # --- 模块三：独立判断和执行"重复收费" ---
                if '重复收费' in task.selected_schemas:
                    from engine.over_standard_v2 import execute_db_rules
                    logger.info(f"为 {hos_id} 开始执行'重复收费'审核 (V2: DB Driven)...")
                    
                    # [V2] 使用新版逻辑引擎 (L1/L2)
                    # 【修正】传入 task.rules.all() 作为 target_rules
                    all_rules_for_task = list(task.rules.all())
                    duplicate_results = execute_db_rules(patient_json, rule_type='重复收费', target_rules=all_rules_for_task)

                    # 保存"重复收费"的结果
                    for res in duplicate_results:
                        is_violation = not res.get('passed', True) or res.get('violation', False)
                        if is_violation:
                            try:
                                rule_info = res.get('rule', {})
                                rule_id = res.get('ruleId') or rule_info.get('rule_id') or 'UNKNOWN_RULE'
                                
                                rule_obj, _ = Rule.objects.get_or_create(
                                    rule_id=rule_id,
                                    defaults={
                                        'drug_name': rule_info.get('drug_name', '重复收费项目'),
                                        'description': rule_info.get('description', ''),
                                        'type': rule_info.get('type', '重复收费')
                                    }
                                )
                                with transaction.atomic():
                                    cleaned_discharge_date = _normalize_discharge_date(patient_json)

                                    reason = res.get('reason', res.get('problem', 'N/A'))

                                    db_result = Result.objects.create(
                                        task=task,
                                        rule=rule_obj,
                                        hospitalization_id=hos_id,
                                        reason=str(reason),
                                        violation_item=json.dumps(res.get('item', {}), ensure_ascii=False, default=str),
                                        discharge_date=cleaned_discharge_date
                                    )
                                    
                                    highlights_data = res.get('highlights', [])
                                    if highlights_data:
                                        logger.info(f"[DuplicateBilling] 为违规结果 {db_result.id} 找到 {len(highlights_data)} 条高亮证据，准备写入数据库。")
                                        for hl in highlights_data:
                                            Highlight.objects.create(
                                                result=db_result,
                                                field_path=hl.get('field_path', 'N/A'),
                                                highlighted_text=str(hl.get('highlighted_text', ''))
                                            )
                                    total_violation_count += 1
                            except Exception as db_error:
                                logger.error(f"保存'重复收费'违规结果时出错: {db_error}", exc_info=True)
                
                # --- 模块四：通用执行“其他类型 / 挂床住院”规则 ---
                if {'其他类型', '挂床住院'}.intersection(task.selected_schemas):
                    from engine.over_standard_v2 import execute_db_rules
                    generic_audit_results = []
                    target_rules = list(task.rules.all())
                    if '其他类型' in task.selected_schemas:
                        logger.info('为 %s 开始执行其他类型审核 (DB Driven)...', hos_id)
                        generic_audit_results += execute_db_rules(
                            patient_json, rule_type='其他类型', target_rules=target_rules,
                        )
                        # 兼容旧版本导入时保存为“其他”的规则。
                        generic_audit_results += execute_db_rules(
                            patient_json, rule_type='其他', target_rules=target_rules,
                        )
                    if '挂床住院' in task.selected_schemas:
                        logger.info('为 %s 开始执行挂床住院审核 (DB Driven)...', hos_id)
                        generic_audit_results += execute_db_rules(
                            patient_json, rule_type='挂床住院', target_rules=target_rules,
                        )
                    other_audit_results = generic_audit_results
                    for res in other_audit_results:
                        is_violation = not res.get('passed', True) or res.get('violation', False)
                        if not is_violation:
                            continue
                        try:
                            rule_info = res.get('rule', {})
                            rule_id = res.get('ruleId') or rule_info.get('rule_id') or 'UNKNOWN_RULE'
                            rule_obj, _ = Rule.objects.get_or_create(
                                rule_id=rule_id,
                                defaults={
                                    'drug_name': rule_info.get('drug_name', '其他类型规则'),
                                    'description': rule_info.get('description', ''),
                                    'type': rule_info.get('type', '其他类型'),
                                },
                            )
                            with transaction.atomic():
                                cleaned_discharge_date = _normalize_discharge_date(patient_json)
                                db_result = Result.objects.create(
                                    task=task,
                                    rule=rule_obj,
                                    hospitalization_id=hos_id,
                                    reason=str(res.get('reason', res.get('problem', 'N/A'))),
                                    violation_item=json.dumps(
                                        res.get('item', {}), ensure_ascii=False, default=str
                                    ),
                                    discharge_date=cleaned_discharge_date,
                                )
                                for hl in res.get('highlights', []):
                                    Highlight.objects.create(
                                        result=db_result,
                                        field_path=hl.get('field_path', 'N/A'),
                                        highlighted_text=str(hl.get('highlighted_text', '')),
                                    )
                                total_violation_count += 1
                        except Exception as db_error:
                            logger.error('保存其他类型违规结果时出错: %s', db_error, exc_info=True)

                processed_count += 1

            except Exception as e:
                logger.error(f"处理住院号 {hos_id} 时发生内部错误: {e}", exc_info=True)
                continue
        
        # --- 3. 任务收尾 ---
        self_reflection = build_task_self_reflection(
            task=task,
            processed_count=processed_count,
            total_violation_count=total_violation_count,
            rule_count=len(all_rules_for_task),
        )
        with transaction.atomic():
            # 重新获取 task 对象，以避免并发问题和状态陈旧
            task_to_complete = Task.objects.get(id=task_id)
            task_to_complete.status = 'completed'
            task_to_complete.summary = f"任务完成。共处理 {processed_count}/{len(task.hospitalization_ids)} 个病例，发现 {total_violation_count} 项违规。"
            task_to_complete.self_reflection = self_reflection
            task_to_complete.save()

    except Task.DoesNotExist:
        logger.error(f"任务ID {task_id} 不存在，无法执行。")
        return

    except Exception as e:
        logger.error(f"任务ID {task_id} 执行过程中发生严重错误: {e}", exc_info=True)
        if task:
            try:
                with transaction.atomic():
                    task_to_fail = Task.objects.get(id=task_id)
                    task_to_fail.status = 'failed'
                    task_to_fail.summary = f"任务执行失败: {str(e)}"
                    task_to_fail.save()
            except Exception as update_error:
                 # 【修正点 2】修复 Pylance 报错
                 logger.error(f"更新任务 {task_id} 状态为 'failed' 时也失败了: {update_error}", exc_info=True)
    
    finally:
        if task:
            final_task = Task.objects.get(id=task_id)
            final_task.completed_at = timezone.now()
            # 只更新这一个字段，避免覆盖掉 summary 等
            final_task.save(update_fields=['completed_at'])
            logger.info(f"任务ID {task.id} 最终状态: {final_task.status}, 已记录完成时间。")
        close_old_connections()
