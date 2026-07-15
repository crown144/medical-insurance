# results/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Result
from .serializers import ResultSerializer
from django.db.models import Min, Q
from django.http import HttpResponse
from urllib.parse import quote
from django.conf import settings
import ast
import json

from accounts.auth import get_request_profile
from cases.models import Case


_RULE_TEMPLATE_INFO = {
    '艾普拉唑': ('YBDR0001', '艾普拉唑用药限定'),
    '醋酸钙': ('YBDR0010', '醋酸钙用药限定'),
    '贝前列素': ('YBDR0012', '贝前列素用药限定'),
    '贝前列素钠': ('YBDR0012', '贝前列素用药限定'),
    '西洛他唑': ('YBDR0013', '西洛他唑用药限定'),
    '金水宝': ('YBDR0021', '金水宝用药限定'),
    '金水宝片': ('YBDR0021', '金水宝用药限定'),
}


class CluePagination(PageNumberPagination):
    """线索列表允许开发页面按需加载更多记录。"""
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 500


def _is_developer_request(request) -> bool:
    profile = get_request_profile(request)
    return bool(profile and profile.role == 'developer')


def _parse_violation_item(value):
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        try:
            parsed = ast.literal_eval(value)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, SyntaxError):
            return {}


def _item_id_part(value, fallback):
    """生成 itemId 段值；空值使用固定占位，避免同一输入重跑时变化。"""
    text = str(value).strip() if value is not None else ''
    return text or fallback


def _charge_date_item_id_part(value):
    """收费日期转换为 yyyyMMdd；不虚构源数据中不存在的时分秒。"""
    digits = ''.join(char for char in str(value or '') if char.isdigit())
    if not digits:
        return 'NO_CHARGE_DATE'
    return digits[:8]


def _build_charge_item_id(rule_id, org_code, hospitalization_id, item_code, charge_date):
    """超限定用药收费明细 itemId：不依赖不存在的收费明细流水号。"""
    return '_'.join([
        _item_id_part(rule_id, 'NO_RULE'),
        _item_id_part(org_code, 'NO_ORG'),
        _item_id_part(hospitalization_id, 'NO_HOSPITALIZATION'),
        _item_id_part(item_code, 'NO_ITEM_CODE'),
        _charge_date_item_id_part(charge_date),
    ])


def _get_rule_template_info(rule):
    """医保控费药品限定类规则按规则库模板返回上报编码与名称。"""
    rule_drug_name = str(getattr(rule, 'drug_name', '') or '').strip()
    for drug_name, info in _RULE_TEMPLATE_INFO.items():
        if drug_name and drug_name in rule_drug_name:
            return info
    return str(getattr(rule, 'rule_id', '') or ''), rule_drug_name


def _filter_by_clue_rule(queryset, keyword):
    """按线索输出的规则编码或规则名称筛选内部 Result 查询集。"""
    keyword = str(keyword or '').strip()
    if not keyword:
        return queryset

    condition = (
        Q(rule__rule_id__icontains=keyword)
        | Q(rule__drug_name__icontains=keyword)
        | Q(rule__description__icontains=keyword)
    )
    keyword_lower = keyword.lower()
    for drug_name, (rule_code, rule_name) in _RULE_TEMPLATE_INFO.items():
        if (
            keyword_lower in rule_code.lower()
            or keyword_lower in rule_name.lower()
            or keyword_lower in drug_name.lower()
        ):
            condition |= Q(rule__drug_name__icontains=drug_name)
    return queryset.filter(condition)


def _build_diagnosis_list(patient_json):
    """将病历中的原始诊断信息转换为上报约定的诊断列表，并去重。"""
    diagnosis_list = []
    seen = set()
    raw_diagnoses = patient_json.get('诊断信息', []) if isinstance(patient_json, dict) else []
    if not isinstance(raw_diagnoses, list):
        return diagnosis_list

    for diagnosis in raw_diagnoses:
        if not isinstance(diagnosis, dict):
            continue
        diagnosis_code = str(
            diagnosis.get('ICD编码') or diagnosis.get('诊断编码') or ''
        ).strip()
        diagnosis_name = str(diagnosis.get('诊断名称') or '').strip()
        if not diagnosis_code and not diagnosis_name:
            continue
        identity = (diagnosis_code, diagnosis_name)
        if identity in seen:
            continue
        seen.add(identity)
        diagnosis_list.append({
            'diagnosisCode': diagnosis_code,
            'diagnosisName': diagnosis_name,
        })
    return diagnosis_list


def _load_diagnosis_lists(results):
    """批量读取结果所对应缓存病历，避免线索导出产生 N+1 次数据库查询。"""
    cache_keys = {}
    for result in results:
        org_code = str(getattr(result.task, 'mdc_org_cd', '') or '').strip()
        hospitalization_id = str(result.hospitalization_id or '').strip()
        cache_key = f'{org_code}:{hospitalization_id}' if org_code else hospitalization_id
        cache_keys[(org_code, hospitalization_id)] = cache_key

    cases_by_key = Case.objects.in_bulk(
        set(cache_keys.values()), field_name='hospitalization_id'
    )
    diagnosis_lists = {}
    for result_key, cache_key in cache_keys.items():
        case = cases_by_key.get(cache_key)
        diagnosis_lists[result_key] = _build_diagnosis_list(
            case.json_content if case else {}
        )
    return diagnosis_lists


def _build_clue(result, diagnosis_list=None):
    """将内部违规结果转换为三医监管可预览的违规结果线索结构。"""
    violation_item = _parse_violation_item(result.violation_item)
    details = violation_item.get('收费明细')
    detail_items = [item for item in details if isinstance(item, dict)] if isinstance(details, list) else []
    first_detail = detail_items[0] if detail_items else {}
    item_name = violation_item.get('收费项目名称') or first_detail.get('收费项目名称') or ''
    item_code = violation_item.get('收费项目代码') or first_detail.get('收费项目代码') or ''
    task = result.task
    # 以下值为本批超限定用药线索的已确认上报值。
    # 一条线索对应同一机构、住院号和规则；收费明细在 clueEvidence 中聚合。
    source_system = '三医联动监管与评价系统'
    rule_code, rule_name = _get_rule_template_info(result.rule)
    org_code = '5605'

    # 没有收费明细时仍返回一条空证据，以便开发页面准确提示缺失字段。
    evidence_sources = detail_items or [{}]
    clue_evidence = []
    for detail in evidence_sources:
        detail_item_code = detail.get('收费项目代码') or item_code or detail.get('ORDER_ITEM_CODE') or ''
        charge_date = detail.get('收费日期') or ''
        clue_evidence.append({
            # 不能用 Result.id、收费报告数组下标或数量/金额生成 itemId。
            'itemId': _build_charge_item_id(
                result.rule.rule_id,
                task.mdc_org_cd,
                result.hospitalization_id,
                detail_item_code,
                charge_date,
            ),
            'hospitalizationId': result.hospitalization_id,
            'dischargeDate': result.discharge_date.strftime('%Y-%m-%d') if result.discharge_date else None,
            'violationItemGenericName': result.rule.drug_name or '',
            'violationItemName': detail.get('收费项目名称') or item_name,
            'violationItemCode': detail_item_code,
            'chargeDate': charge_date,
            'quantity': detail.get('项目数量') or detail.get('数量') or '',
            'unitPrice': detail.get('项目单价') or '',
            'amount': detail.get('项目费用') or detail.get('金额') or '',
            'unit': detail.get('项目单位') or '',
            'violationReason': result.reason or '',
            'diagnosisList': diagnosis_list or [],
        })

    return {
        '_internalResultId': result.id,
        'externalClueId': f'{source_system}_{rule_code}_{org_code}_{result.hospitalization_id}',
        'sourceSystem': source_system,
        'clueType': 'STRUCTURED',
        'ruleCode': rule_code,
        'ruleName': rule_name,
        'evidenceVersion': 'v20260712',
        'orgCode': org_code,
        'orgName': '海南医科大学第一附属医院',
        'evidenceType': 'SINGLE' if len(clue_evidence) == 1 else 'MULTIPLE',
        'evidenceCount': len(clue_evidence),
        'cluePrompt': result.reason or '',
        'clueEvidence': clue_evidence,
    }


def _merge_clues(clues):
    """同一机构、住院号、规则只输出一条线索，收费明细合并为证据数组。"""
    merged_by_external_id = {}
    for clue in clues:
        external_clue_id = clue['externalClueId']
        existing = merged_by_external_id.get(external_clue_id)
        if existing is None:
            merged_by_external_id[external_clue_id] = clue
            continue
        existing['clueEvidence'].extend(clue['clueEvidence'])

    merged_clues = list(merged_by_external_id.values())
    for clue in merged_clues:
        evidence_count = len(clue['clueEvidence'])
        clue['evidenceCount'] = evidence_count
        clue['evidenceType'] = 'SINGLE' if evidence_count == 1 else 'MULTIPLE'
    return merged_clues


class ResultViewSet(viewsets.ReadOnlyModelViewSet): # 只读，不允许通过API修改或删除结果
    queryset = Result.objects.all().prefetch_related('highlights').order_by('-created_at')
    serializer_class = ResultSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {
        'task_id': ['exact'],
        'hospitalization_id': ['exact', 'icontains'],   # 支持住院号精确和模糊查询
        'rule__drug_name': ['icontains'],      # 支持药品名模糊查询
        'discharge_date': ['year', 'month'],   # 支持按出院年、月精确查询
    }
    def get_queryset(self):
        queryset = super().get_queryset() # 这会获取到上面带有 prefetch_related 的 queryset
        
        # 检查是否是多检测模式（通过task_id参数判断）
        task_id = self.request.query_params.get('task_id')
        
        if task_id:
            queryset = queryset.filter(task_id=task_id)
        
        # 统一去重策略：基于 (住院号, 规则ID, 违规原因, 违规项目) 的精细化去重
        # 1. 必须先清除默认排序
        queryset_no_order = queryset.order_by()
        
        # 2. 分组并获取每组最小 ID
        # 将 violation_item 加入分组，确保不同的违规项目（即使规则相同）都被保留，
        # 同时相同的违规项目（完全重复的数据）被去除。
        values = queryset_no_order.values(
            'task_id', 
            'hospitalization_id', 
            'rule_id', 
            'reason', 
            'violation_item'  # <--- 关键修改：加入此字段
        ).annotate(min_id=Min('id'))
        
        # 3. 提取出所有这些最小的 ID
        pks_to_keep = [item['min_id'] for item in values]

        # 4. 重新构建最终的 QuerySet
        final_queryset = queryset.filter(pk__in=pks_to_keep)
        return final_queryset

    @action(detail=False, methods=['get'], url_path='clues')
    def clues(self, request):
        """开发用户查看内部结果转换后的结构化违规线索。"""
        if not _is_developer_request(request):
            return Response({'detail': '仅开发用户可查看违规结果线索。'}, status=status.HTTP_403_FORBIDDEN)

        queryset = self.filter_queryset(self.get_queryset()).select_related('task', 'rule')
        queryset = _filter_by_clue_rule(queryset, request.query_params.get('rule_keyword'))
        results = list(queryset)
        diagnosis_lists = _load_diagnosis_lists(results)
        clues = _merge_clues([
            _build_clue(
                result,
                diagnosis_lists.get(
                    (str(result.task.mdc_org_cd or '').strip(), str(result.hospitalization_id or '').strip()),
                    [],
                ),
            )
            for result in results
        ])
        # 不使用全局分页器（其 PAGE_SIZE 固定为 10，且不接受 page_size），
        # 否则前端选择 50/100/200 条仍会始终只收到 10 条。
        paginator = CluePagination()
        page = paginator.paginate_queryset(clues, request, view=self)
        if page is not None:
            return paginator.get_paginated_response(page)
        return Response(clues)

    
    @action(detail=False, methods=['get'], url_path='download-json-report')
    def download_json_report(self, request):
        """下载指定任务和住院号的 JSON 格式违规报告。"""
        task_id = request.query_params.get('task_id')
        hospitalization_id = request.query_params.get('hospitalization_id')
        
        if not hospitalization_id:
            return Response({'error': '缺少hospitalization_id参数'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 构建查询条件 - 必须同时指定task_id和hospitalization_id以确保数据准确性
        if not task_id:
            return Response({'error': '缺少task_id参数'}, status=status.HTTP_400_BAD_REQUEST)
            
        filter_conditions = {
            'hospitalization_id': hospitalization_id,
            'task_id': task_id
        }
        
        # 获取指定条件的违规结果
        results = Result.objects.filter(**filter_conditions).select_related('rule')
        
        violations_data = []
        for result in results:
            violations_data.append({
                "住院号": result.hospitalization_id,
                "违规项目": result.violation_item,
                "违规原因": result.reason,
                "有关依据": result.rule.description if result.rule else "N/A"
            })
        
        json_string = json.dumps(violations_data, ensure_ascii=False, indent=2)
        response = HttpResponse(json_string, content_type='application/json; charset=utf-8')
        filename = f"违规报告_任务{task_id}_{hospitalization_id}.json"
        response['Content-Disposition'] = f"attachment; filename*=utf-8''{quote(filename)}"
        return response
    
    @action(detail=False, methods=['get'], url_path='download-txt-report')
    def download_txt_report(self, request):
        """下载指定任务和住院号的 TXT 格式文本报告。"""
        task_id = request.query_params.get('task_id')
        hospitalization_id = request.query_params.get('hospitalization_id')
        
        if not hospitalization_id:
            return Response({'error': '缺少hospitalization_id参数'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 构建查询条件 - 必须同时指定task_id和hospitalization_id以确保数据准确性
        if not task_id:
            return Response({'error': '缺少task_id参数'}, status=status.HTTP_400_BAD_REQUEST)
            
        filter_conditions = {
            'hospitalization_id': hospitalization_id,
            'task_id': task_id
        }
        
        # 获取指定条件的违规结果
        results = Result.objects.filter(**filter_conditions).select_related('rule')
        
        if not results.exists():
            report_content = f"住院号 {hospitalization_id} 在任务 {task_id or 'all'} 中未发现违规情况。"
        else:
            report_lines = [f"医保审核报告 - 任务{task_id or 'all'} - 住院号{hospitalization_id}", "=" * 60]
            for index, result in enumerate(results, 1):
                report_lines.append(f"\n--- 违规项 {index} ---")
                report_lines.append(f"项目: {result.violation_item}")
                report_lines.append(f"规则: {result.rule.description if result.rule else 'N/A'}")
                report_lines.append(f"违规原因: {result.reason}")
            report_lines.append("\n" + "=" * 60)
            report_lines.append(f"总结: 住院号 {hospitalization_id} 共发现 {results.count()} 项违规")
            report_lines.append("=" * 60)
            report_content = "\n".join(report_lines)
        
        response = HttpResponse(report_content, content_type='text/plain; charset=utf-8')
        filename = f"审核报告_任务{task_id}_{hospitalization_id}.txt"
        response['Content-Disposition'] = f"attachment; filename*=utf-8''{quote(filename)}"
        return response
