import logging
import json
import os
import random
from celery import shared_task
from django.utils import timezone
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


def _demo_patient_data(hospitalization_id: str, mdc_org_cd: str = None):
    cache_key = f"{mdc_org_cd}:{hospitalization_id}" if mdc_org_cd else hospitalization_id
    cache_keys = [cache_key]
    if cache_key != hospitalization_id:
        cache_keys.append(hospitalization_id)

    for current_key in cache_keys:
        try:
            case = Case.objects.get(pk=current_key)
            logger.info(f"Demo: hit cases_case for {hospitalization_id}")
            return case.json_content
        except Case.DoesNotExist:
            continue

    demo_case = os.path.join(settings.BASE_DIR, "mock_patient_data", f"{hospitalization_id}.json")
    if os.path.exists(demo_case):
        with open(demo_case, 'r', encoding='utf-8') as f:
            logger.info(f"Demo: loaded mock_patient_data for {hospitalization_id}")
            patient_json = json.load(f)
            try:
                Case.objects.update_or_create(
                    hospitalization_id=cache_key,
                    defaults={'json_content': patient_json},
                )
            except Exception:
                pass
            return patient_json

    raise FileNotFoundError("Demo环境未找到病例数据")


def get_patient_data(hospitalization_id: str, mdc_org_cd: str = None):
    """
    数据获取辅助函数，增加了缓存逻辑，并通过“猴子补丁”注入配置。
    """
    # --- 1. 尝试从缓存读取 ---
    if getattr(settings, 'DEMO_MODE', False):
        return _demo_patient_data(hospitalization_id, mdc_org_cd)

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
                                    discharge_date_str = patient_json.get('出院记录', {}).get('出院日期') or patient_json.get('基本信息', {}).get('出院日期')
                                    cleaned_discharge_date = discharge_date_str if discharge_date_str and discharge_date_str not in ['xxx', '文本中未提及该内容'] else None
                                    
                                    # 新格式使用 reason，旧格式使用 problem
                                    reason = res.get('reason', res.get('problem', 'N/A'))
                                    
                                    db_result = Result.objects.create(
                                        task=task,
                                        rule=rule_obj,
                                        hospitalization_id=hos_id,
                                        reason=str(reason),
                                        violation_item=str(res.get('item', {})),
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
                                    discharge_date_str = patient_json.get('出院记录', {}).get('出院日期') or patient_json.get('基本信息', {}).get('出院日期')
                                    cleaned_discharge_date = discharge_date_str if discharge_date_str and discharge_date_str not in ['xxx', '文本中未提及该内容'] else None

                                    reason = res.get('reason', res.get('problem', 'N/A'))

                                    db_result = Result.objects.create(
                                        task=task,
                                        rule=rule_obj,
                                        hospitalization_id=hos_id,
                                        reason=str(reason),
                                        violation_item=str(res.get('item', {})),
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
                                    discharge_date_str = patient_json.get('出院记录', {}).get('出院日期') or patient_json.get('基本信息', {}).get('出院日期')
                                    cleaned_discharge_date = discharge_date_str if discharge_date_str and discharge_date_str not in ['xxx', '文本中未提及该内容'] else None

                                    reason = res.get('reason', res.get('problem', 'N/A'))

                                    db_result = Result.objects.create(
                                        task=task,
                                        rule=rule_obj,
                                        hospitalization_id=hos_id,
                                        reason=str(reason),
                                        violation_item=str(res.get('item', {})),
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
                
                processed_count += 1

            except Exception as e:
                logger.error(f"处理住院号 {hos_id} 时发生内部错误: {e}", exc_info=True)
                continue
        
        # --- 3. 任务收尾 ---
        with transaction.atomic():
            # 重新获取 task 对象，以避免并发问题和状态陈旧
            task_to_complete = Task.objects.get(id=task_id)
            task_to_complete.status = 'completed'
            task_to_complete.summary = f"任务完成。共处理 {processed_count}/{len(task.hospitalization_ids)} 个病例，发现 {total_violation_count} 项违规。"
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
