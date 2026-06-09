import json
import re
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Optional, Tuple

from results.models import Result

from ..models import FeiJianImportBatch, FeiJianRawRecord


CATEGORY_ALIASES = {
    '分解住院': [
        '分解住院', '拆分住院', '二次住院', '重复住院', '低标准入院',
    ],
    '挂床住院': [
        '挂床住院', '虚挂床位', '不在院', '无诊疗记录', '空床住院',
    ],
    '虚假住院': [
        '虚假住院', '伪造住院', '冒名住院', '假住院', '无实际住院',
    ],
    '超限定用药': [
        '超限定用药', '超限用药', '超医保限定', '限定支付范围',
        '适应症不符', '超适应症', '超范围用药', '用药限制',
    ],
    '超标准收费': [
        '超标准收费', '超标收费', '超价格收费', '收费超标',
        '床位费超标', '护理费超标', '超过收费标准',
    ],
    '重复收费': [
        '重复收费', '重复计费', '重复收取', '重复项目', '重复结算',
    ],
    '过度检查': [
        '过度检查', '无指征检查', '过度诊疗', '过度检验', '检查过度',
    ],
    '串换项目': [
        '串换项目', '串换药品', '串换诊疗项目', '项目串换',
        '药品串换', '目录串换',
    ],
    '违规收费': [
        '违规收费', '不合理收费', '违规结算', '违规费用',
    ],
}

CATEGORY_BY_KEYWORD = {
    alias: canonical
    for canonical, aliases in CATEGORY_ALIASES.items()
    for alias in aliases
}

MATCHED = 'matched'
PARTIAL = 'partial'
UNMATCHED = 'unmatched'
SYSTEM_ONLY = 'system-only'

MATCH_STATUS_LABELS = {
    MATCHED: '完全匹配',
    PARTIAL: '部分匹配',
    UNMATCHED: '仅飞检发现',
    SYSTEM_ONLY: '系统额外发现',
}


def align_batch_results(
    batch: FeiJianImportBatch,
    task_id: Optional[int] = None,
) -> Dict[str, Any]:
    if task_id is None:
        task_id = _infer_task_id(batch)

    feijian_records = list(
        batch.records.exclude(hospitalization_no='').order_by('row_index', 'id'),
    )
    if not feijian_records:
        return _empty_response(batch, task_id, '当前导入批次没有可对齐的住院号')

    hospitalization_ids = sorted({r.hospitalization_no for r in feijian_records})
    system_results = list(
        Result.objects.filter(
            task_id=task_id,
            hospitalization_id__in=hospitalization_ids,
        ).select_related('rule').order_by('hospitalization_id', 'id')
    ) if task_id else []

    results_by_hos: Dict[str, List[Result]] = {}
    for result in system_results:
        results_by_hos.setdefault(result.hospitalization_id, []).append(result)

    used_result_ids = set()
    alignments = []

    for record in feijian_records:
        candidates = [
            result for result in results_by_hos.get(record.hospitalization_no, [])
            if result.id not in used_result_ids
        ]
        best_result, score, reasons = _find_best_match(record, candidates)

        if best_result and score >= 0.45:
            used_result_ids.add(best_result.id)
            status = MATCHED if score >= 0.75 else PARTIAL
            alignments.append(_build_alignment(record, best_result, status, score, reasons))
        else:
            alignments.append(_build_alignment(record, None, UNMATCHED, score, reasons))

    feijian_hos_ids = {record.hospitalization_no for record in feijian_records}
    for result in system_results:
        if result.id in used_result_ids:
            continue
        if result.hospitalization_id not in feijian_hos_ids:
            continue
        alignments.append(_build_system_only_alignment(result))

    summary = _build_summary(alignments)
    return {
        'batch_id': batch.id,
        'task_id': task_id,
        'summary': summary,
        'items': alignments,
    }


def _infer_task_id(batch: FeiJianImportBatch) -> Optional[int]:
    ids = [
        value for value in
        batch.records.exclude(audit_task_id='').values_list('audit_task_id', flat=True)
        if str(value).strip().isdigit()
    ]
    if not ids:
        return None
    counts: Dict[int, int] = {}
    for value in ids:
        task_id = int(value)
        counts[task_id] = counts.get(task_id, 0) + 1
    return max(counts.items(), key=lambda item: item[1])[0]


def _find_best_match(
    record: FeiJianRawRecord,
    candidates: Iterable[Result],
) -> Tuple[Optional[Result], float, List[str]]:
    best_result = None
    best_score = 0.0
    best_reasons: List[str] = []

    for result in candidates:
        score, reasons = _score_pair(record, result)
        if score > best_score:
            best_result = result
            best_score = score
            best_reasons = reasons

    return best_result, best_score, best_reasons


def _score_pair(record: FeiJianRawRecord, result: Result) -> Tuple[float, List[str]]:
    reasons = ['住院号一致']
    feijian_text = _join_text(record.issue_category, record.issue_description)
    system_text = _join_text(
        getattr(result.rule, 'type', ''),
        getattr(result.rule, 'drug_name', ''),
        getattr(result.rule, 'description', ''),
        result.reason,
        result.violation_item,
    )

    feijian_category = canonical_category(feijian_text)
    system_category = canonical_category(system_text)

    score = 0.25
    if feijian_category and feijian_category == system_category:
        score += 0.45
        reasons.append('问题类型归一后一致')
    elif feijian_category and system_category:
        score += 0.12
        reasons.append('双方问题类型可识别但不完全一致')

    text_score = text_similarity(feijian_text, system_text)
    score += min(text_score * 0.25, 0.25)
    if text_score >= 0.35:
        reasons.append('问题描述文本相似')

    amount_score = amount_similarity(record.involved_amount, _extract_amount(system_text))
    if amount_score is not None:
        score += amount_score * 0.05
        if amount_score >= 0.8:
            reasons.append('金额接近')

    return min(score, 1.0), reasons


def canonical_category(text: Any) -> str:
    normalized = normalize_text(text)
    if not normalized:
        return ''
    for keyword, canonical in CATEGORY_BY_KEYWORD.items():
        if normalize_text(keyword) in normalized:
            return canonical
    return ''


def normalize_text(value: Any) -> str:
    if value is None:
        return ''
    text = _stringify(value)
    text = text.lower()
    text = re.sub(r'\s+', '', text)
    text = re.sub(r'[，。、“”‘’：:；;（）()\[\]{}【】\-_/\\|,.\s]+', '', text)
    return text


def text_similarity(left: Any, right: Any) -> float:
    left_text = normalize_text(left)
    right_text = normalize_text(right)
    if not left_text or not right_text:
        return 0.0

    left_tokens = _tokens(left_text)
    right_tokens = _tokens(right_text)
    if left_tokens and right_tokens:
        overlap = len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)
    else:
        overlap = 0.0

    sequence = SequenceMatcher(None, left_text, right_text).ratio()
    return max(overlap, sequence)


def amount_similarity(left: Decimal, right: Optional[Decimal]) -> Optional[float]:
    if right is None:
        return None
    left = Decimal(left or 0)
    if left == 0 and right == 0:
        return 1.0
    denominator = max(abs(left), abs(right), Decimal('1'))
    diff_ratio = abs(left - right) / denominator
    return float(max(Decimal('0'), Decimal('1') - diff_ratio))


def _extract_amount(text: Any) -> Optional[Decimal]:
    raw = _stringify(text)
    matches = re.findall(r'\d+(?:,\d{3})*(?:\.\d+)?', raw)
    if not matches:
        return None
    values = []
    for match in matches:
        try:
            values.append(Decimal(match.replace(',', '')))
        except Exception:
            pass
    if not values:
        return None
    return max(values)


def _tokens(text: str) -> set:
    tokens = set()
    for size in (2, 3, 4):
        tokens.update(text[i:i + size] for i in range(max(len(text) - size + 1, 0)))
    return {token for token in tokens if token}


def _build_alignment(
    record: FeiJianRawRecord,
    result: Optional[Result],
    status: str,
    score: float,
    reasons: List[str],
) -> Dict[str, Any]:
    system_category = canonical_category(_system_text(result)) if result else ''
    feijian_category = canonical_category(_join_text(record.issue_category, record.issue_description))
    return {
        'id': f'f{record.id}-s{result.id if result else "none"}',
        'feijianRecordId': record.id,
        'systemResultId': result.id if result else None,
        'auditTaskId': str(result.task_id if result else record.audit_task_id),
        'hospitalizationNo': record.hospitalization_no,
        'patientName': record.patient_name,
        'hospitalName': record.hospital_name,
        'feijianIssue': record.issue_description or record.issue_category,
        'feijianAmount': float(record.involved_amount or 0),
        'feijianCategory': feijian_category or record.issue_category,
        'systemIssue': _system_issue(result),
        'systemAmount': float(_extract_amount(_system_text(result)) or 0),
        'systemCategory': system_category,
        'matchStatus': status,
        'matchStatusLabel': MATCH_STATUS_LABELS[status],
        'matchScore': round(score, 3),
        'matchReasons': reasons,
    }


def _build_system_only_alignment(result: Result) -> Dict[str, Any]:
    system_text = _system_text(result)
    return {
        'id': f'fnone-s{result.id}',
        'feijianRecordId': None,
        'systemResultId': result.id,
        'auditTaskId': str(result.task_id),
        'hospitalizationNo': result.hospitalization_id,
        'patientName': '',
        'hospitalName': '',
        'feijianIssue': '',
        'feijianAmount': 0,
        'feijianCategory': '',
        'systemIssue': _system_issue(result),
        'systemAmount': float(_extract_amount(system_text) or 0),
        'systemCategory': canonical_category(system_text),
        'matchStatus': SYSTEM_ONLY,
        'matchStatusLabel': MATCH_STATUS_LABELS[SYSTEM_ONLY],
        'matchScore': 0,
        'matchReasons': ['同住院号下未找到对应飞检问题'],
    }


def _build_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(items)
    matched = sum(1 for item in items if item['matchStatus'] == MATCHED)
    partial = sum(1 for item in items if item['matchStatus'] == PARTIAL)
    unmatched = sum(1 for item in items if item['matchStatus'] == UNMATCHED)
    system_only = sum(1 for item in items if item['matchStatus'] == SYSTEM_ONLY)
    aligned = matched + partial
    return {
        'total': total,
        'matched': matched,
        'partial': partial,
        'unmatched': unmatched,
        'systemOnly': system_only,
        'alignmentRate': round(aligned * 100 / total, 2) if total else 0,
        'diffCount': unmatched + system_only + partial,
        'unresolvedDiffCount': unmatched + system_only + partial,
    }


def _empty_response(
    batch: FeiJianImportBatch,
    task_id: Optional[int],
    message: str,
) -> Dict[str, Any]:
    return {
        'batch_id': batch.id,
        'task_id': task_id,
        'summary': {
            'total': 0,
            'matched': 0,
            'partial': 0,
            'unmatched': 0,
            'systemOnly': 0,
            'alignmentRate': 0,
            'diffCount': 0,
            'unresolvedDiffCount': 0,
            'message': message,
        },
        'items': [],
    }


def _system_issue(result: Optional[Result]) -> str:
    if not result:
        return ''
    return result.reason or result.violation_item or getattr(result.rule, 'description', '') or ''


def _system_text(result: Optional[Result]) -> str:
    if not result:
        return ''
    return _join_text(
        getattr(result.rule, 'type', ''),
        getattr(result.rule, 'drug_name', ''),
        getattr(result.rule, 'description', ''),
        result.reason,
        result.violation_item,
    )


def _join_text(*values: Any) -> str:
    return ' '.join(_stringify(value) for value in values if value not in [None, ''])


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)
