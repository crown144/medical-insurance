import json
import os
import re
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Optional, Tuple

from openai import OpenAI
from results.models import Result
from rules.services.agenta_service import AgentAService

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
        '限定用药', '限适应症', '限制用药',
        'restricted medication use', 'restricted medication',
        'indication mismatch', 'drug indication mismatch',
        'drug indication', 'limited indication', 'indication restriction',
        'requires hyperphosphatemia', 'requires duodenal ulcer',
        'reflux esophagitis', 'calcium acetate', 'ilaprazole',
    ],
    '超标准收费': [
        '超标准收费', '超标收费', '超价格收费', '收费超标',
        '床位费超标', '护理费超标', '超过收费标准',
        'over-standard charge', 'over standard charge', 'overcharge',
        'charge exceeds standard', 'price exceeds standard',
    ],
    '重复收费': [
        '重复收费', '重复计费', '重复收取', '重复项目', '重复结算',
        'duplicate charge', 'duplicate billing', 'duplicate item',
        'repeated billing', 'repeated charge',
    ],
    '过度检查': [
        '过度检查', '无指征检查', '过度诊疗', '过度检验', '检查过度',
        'overutilization', 'over examination', 'excessive examination',
        'unnecessary examination', 'over testing',
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

CROSS_LANGUAGE_TERMS = [
    ('calcium acetate', '醋酸钙'),
    ('calcium acetate tablets', '醋酸钙'),
    ('hyperphosphatemia', '高磷血症'),
    ('ilaprazole', '艾普拉唑'),
    ('duodenal ulcer', '十二指肠溃疡'),
    ('reflux esophagitis', '反流性食管炎'),
    ('intravenous injection', '静脉注射'),
    ('venous blood collection', '静脉采血'),
    ('arterial pressure injection', '动脉加压注射'),
    ('arterial blood collection', '动脉采血'),
    ('gastrointestinal decompression', '胃肠减压'),
    ('special ear treatment', '耳部特殊治疗'),
    ('mechanical assisted sputum clearance', '机械辅助排痰'),
]

MATCHED = 'matched'
PARTIAL = 'partial'
UNMATCHED = 'unmatched'
SYSTEM_ONLY = 'system-only'
LLM_TOP_CANDIDATE_COUNT = 3

MATCH_STATUS_LABELS = {
    MATCHED: '完全匹配',
    PARTIAL: '部分匹配',
    UNMATCHED: '仅飞检发现',
    SYSTEM_ONLY: '系统额外发现',
}


def align_batch_results(
    batch: FeiJianImportBatch,
    task_id: Optional[int] = None,
    use_llm: bool = False,
    record_offset: Optional[int] = None,
    record_limit: Optional[int] = None,
) -> Dict[str, Any]:
    if task_id is None:
        task_id = _infer_task_id(batch)

    record_qs = batch.records.exclude(hospitalization_no='').order_by('row_index', 'id')
    total_records = record_qs.count()
    if record_offset is not None and record_limit is not None:
        record_qs = record_qs[record_offset:record_offset + record_limit]

    feijian_records = list(record_qs)
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
    llm_cache: Dict[str, Tuple[float, str]] = {}
    llm_enabled = use_llm and _has_llm_config()

    for record in feijian_records:
        candidates = results_by_hos.get(record.hospitalization_no, [])
        best_result, score, reasons = _find_best_match(
            record,
            candidates,
            llm_cache=llm_cache if llm_enabled else None,
        )

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
        'llm_enabled': llm_enabled,
        'summary': summary,
        'items': alignments,
        'total_records': total_records,
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
    llm_cache: Optional[Dict[str, Tuple[float, str]]] = None,
) -> Tuple[Optional[Result], float, List[str]]:
    best_result = None
    best_score = 0.0
    best_reasons: List[str] = []
    scored_candidates = []

    for result in candidates:
        score, reasons = _score_pair(record, result)
        scored_candidates.append((result, score, reasons))
        if score > best_score:
            best_result = result
            best_score = score
            best_reasons = reasons

    if llm_cache is not None and scored_candidates and best_score < 0.75:
        top_candidates = sorted(
            scored_candidates,
            key=lambda item: item[1],
            reverse=True,
        )[:LLM_TOP_CANDIDATE_COUNT]
        for result, score, reasons in top_candidates:
            llm_score, llm_reason = _llm_score_pair(record, result, llm_cache)
            if llm_score is None:
                continue
            merged_reasons = reasons[:]
            if llm_reason:
                merged_reasons.append(f'大模型复核：{llm_reason}')
            candidate_score = llm_score if score < 0.75 else max(score, llm_score)
            if candidate_score > best_score:
                best_result = result
                best_score = candidate_score
                best_reasons = merged_reasons

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

    if _has_cross_language_term_match(feijian_text, system_text):
        score += 0.12
        reasons.append('关键药品/项目中英文一致')

    amount_score = amount_similarity(record.involved_amount, _extract_amount(system_text))
    if amount_score is not None:
        score += amount_score * 0.05
        if amount_score >= 0.8:
            reasons.append('金额接近')

    return min(score, 1.0), reasons


def _has_llm_config() -> bool:
    config = AgentAService._llm_config()
    return bool(config.get('api_key') and config.get('base_url') and config.get('model'))


def _llm_score_pair(
    record: FeiJianRawRecord,
    result: Result,
    cache: Dict[str, Tuple[float, str]],
) -> Tuple[Optional[float], str]:
    cache_key = f'{record.id}:{result.id}'
    if cache_key in cache:
        return cache[cache_key]

    feijian_text = _join_text(record.issue_category, record.issue_description)
    system_text = _system_text(result)
    prompt = f"""你是医保飞检结果与系统审查结果的对齐专家。请判断同一住院号下，两条问题是否指向同一个医保违规问题。

判断原则：
1. 飞检问题名称和系统问题名称可以不同，只要业务含义一致即可匹配。
2. 重点看问题类型、疾病/适应症、药品/收费项目、违规原因是否一致。
3. “限某疾病/某适应症/事中审核”通常可能对应系统中的“适应症不符/超限定用药”，但不能只因为都有“事中审核”就匹配。
4. 金额可以辅助判断，但金额不同不一定代表不匹配。
5. 只返回 JSON，不要返回解释文本。

飞检记录：
- 住院号：{record.hospitalization_no}
- 患者：{record.patient_name}
- 问题类别：{record.issue_category}
- 问题描述：{record.issue_description}
- 涉及金额：{record.involved_amount}

系统结果：
- 规则类型：{getattr(result.rule, 'type', '')}
- 规则名称：{getattr(result.rule, 'drug_name', '')}
- 规则描述：{getattr(result.rule, 'description', '')}
- 系统问题：{_system_issue(result)}
- 违规项目：{result.violation_item or ''}

返回格式：
{{"match": true, "score": 0.86, "reason": "同为高磷血症相关超限定用药"}}
""".strip()

    try:
        config = AgentAService._llm_config()
        client = OpenAI(
            api_key=config['api_key'],
            base_url=config['base_url'],
            timeout=float(os.environ.get('FEIJIAN_ALIGNMENT_LLM_TIMEOUT') or 20),
        )
        response = client.chat.completions.create(
            model=os.environ.get('FEIJIAN_ALIGNMENT_MODEL') or config['model'],
            messages=[
                {
                    'role': 'system',
                    'content': '你只输出严格 JSON。score 必须是 0 到 1 的数字。/no_think',
                },
                {'role': 'user', 'content': f'{prompt}\n/no_think'},
            ],
            temperature=0,
            max_tokens=int(os.environ.get('FEIJIAN_ALIGNMENT_MAX_TOKENS') or 300),
            extra_body={'enable_thinking': False},
        )
        raw = response.choices[0].message.content or ''
        data = _parse_llm_json(raw)
        if not data:
            return None, ''

        is_match = bool(data.get('match'))
        raw_score = data.get('score', 0)
        score = max(0.0, min(float(raw_score), 1.0))
        if not is_match:
            score = min(score, 0.4)
        reason = _stringify(data.get('reason') or '').strip()
        cache[cache_key] = (score, reason)
        return cache[cache_key]
    except Exception:
        return None, ''


def _parse_llm_json(raw: str) -> Optional[Dict[str, Any]]:
    raw = raw.strip()
    if raw.startswith('```'):
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
    match = re.search(r'\{[\s\S]*\}', raw)
    if match:
        raw = match.group(0)
    try:
        data = json.loads(raw)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def canonical_category(text: Any) -> str:
    normalized = normalize_text(text)
    if not normalized:
        return ''
    for keyword, canonical in CATEGORY_BY_KEYWORD.items():
        if normalize_text(keyword) in normalized:
            return canonical
    if _looks_like_limited_indication(normalized):
        return '超限定用药'
    return ''


def normalize_text(value: Any) -> str:
    if value is None:
        return ''
    text = _stringify(value)
    text = text.lower()
    text = re.sub(r'\s+', '', text)
    text = re.sub(r'[，。、“”‘’：:；;（）()\[\]{}【】\-_/\\|,.\s]+', '', text)
    return text


def _has_cross_language_term_match(left: Any, right: Any) -> bool:
    left_text = normalize_text(left)
    right_text = normalize_text(right)
    if not left_text or not right_text:
        return False
    for english, chinese in CROSS_LANGUAGE_TERMS:
        english_text = normalize_text(english)
        chinese_text = normalize_text(chinese)
        if (
            (english_text in left_text and chinese_text in right_text)
            or (chinese_text in left_text and english_text in right_text)
        ):
            return True
    return False


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
    common = _common_substring_score(left_text, right_text)
    return max(overlap, sequence, common)


def _looks_like_limited_indication(text: str) -> bool:
    if '限' not in text:
        return False
    medical_hint = any(keyword in text for keyword in ['症', '病', '炎', '癌', '瘤', '用药', '药', '适应'])
    audit_hint = any(keyword in text for keyword in ['审核', '限定', '超限', '医保'])
    return medical_hint or audit_hint


def _common_substring_score(left: str, right: str) -> float:
    matcher = SequenceMatcher(None, left, right)
    longest = matcher.find_longest_match(0, len(left), 0, len(right)).size
    if longest < 3:
        return 0.0
    return min(longest / max(min(len(left), len(right)), 1), 1.0)


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
    feijian_text = _join_text(record.issue_category, record.issue_description)
    system_text = _system_text(result)
    system_category = canonical_category(system_text) if result else ''
    feijian_category = canonical_category(feijian_text)
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
        'systemAmount': float(_extract_amount(system_text) or 0),
        'systemCategory': system_category,
        'matchStatus': status,
        'matchStatusLabel': MATCH_STATUS_LABELS[status],
        'matchScore': round(score, 3),
        'matchReasons': reasons,
        'matchDebug': {
            'feijianText': feijian_text,
            'systemText': system_text,
            'feijianNormalizedText': normalize_text(feijian_text),
            'systemNormalizedText': normalize_text(system_text),
            'feijianNormalizedCategory': feijian_category,
            'systemNormalizedCategory': system_category,
        },
    }


def _build_system_only_alignment(result: Result) -> Dict[str, Any]:
    system_text = _system_text(result)
    system_category = canonical_category(system_text)
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
        'systemCategory': system_category,
        'matchStatus': SYSTEM_ONLY,
        'matchStatusLabel': MATCH_STATUS_LABELS[SYSTEM_ONLY],
        'matchScore': 0,
        'matchDebug': {
            'feijianText': '',
            'systemText': system_text,
            'feijianNormalizedText': '',
            'systemNormalizedText': normalize_text(system_text),
            'feijianNormalizedCategory': '',
            'systemNormalizedCategory': system_category,
        },
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


def _translate_reason(text: str) -> str:
    """Translate known Chinese reason patterns to English."""
    if not text:
        return text

    term_translations = {
        '艾普拉唑': 'ilaprazole',
        '醋酸钙': 'calcium acetate tablets',
        '静脉注射': 'intravenous injection',
        '静脉采血': 'venous blood collection',
        '动脉加压注射': 'arterial pressure injection',
        '动脉采血': 'arterial blood collection',
        '机械辅助排痰': 'mechanical assisted sputum clearance',
        '胃肠减压': 'gastrointestinal decompression',
        '急诊监护费': 'emergency monitoring fee',
        '急诊诊查费': 'emergency consultation fee',
    }
    translations = {
        '规则校验通过，未发现异常。': 'Rule check passed, no anomalies found.',
        '发现拦截条件：诊断命中且存在新发/急性证据。': 'Interception: diagnosis matches with new/acute evidence.',
        '未发现拦截条件。': 'No interception condition found.',
        '适应症不符：艾普拉唑限十二指肠溃疡或反流性食管炎，未发现相关诊断或病史支持':
            'Indication mismatch: ilaprazole is limited to duodenal ulcer or reflux esophagitis, and no supporting diagnosis or medical history was found.',
        '适应症不符：醋酸钙限高磷血症患者使用，未发现相关诊断或病史支持':
            'Indication mismatch: calcium acetate tablets are limited to patients with hyperphosphatemia, and no supporting diagnosis or medical history was found.',
        '“静脉注射”与“静脉采血”不能同时开':
            'Intravenous injection and venous blood collection cannot be ordered at the same time.',
        '“动脉加压注射”与“动脉采血”不能同时开':
            'Arterial pressure injection and arterial blood collection cannot be ordered at the same time.',
        '单日不得与急诊诊查费同时收费':
            'May not be charged together with emergency consultation fee on the same day.',
    }
    if text in translations:
        return translations[text]

    m = re.match(r'^(.+?)与(.+?)在同一秒内同时开具，冲突时间点[:：](.+)$', text)
    if m:
        first = term_translations.get(m.group(1).strip(), m.group(1).strip())
        second = term_translations.get(m.group(2).strip(), m.group(2).strip())
        details = m.group(3)
        for cn, en in term_translations.items():
            details = details.replace(cn, en)
        details = details.replace('；', '; ').replace('，', ', ').replace('项', ' item(s)')
        return f'{first} and {second} were ordered in the same second. Conflict time point(s): {details}'

    m = re.match(r'^(.+?)项目单日上限为(.+?)，发现超限记录[:：](.+?)(。|$)', text)
    if m:
        item = term_translations.get(m.group(1).strip(), m.group(1).strip())
        return f'{item} exceeds the daily limit of {m.group(2)}.'

    # 收费项目"xxx"(代码:xxx)在xxx存在组套重复收费，涉及xxx，总金额:xxx元
    m = re.match(r'收费项目"(.+?)"\(代码:(.+?)\)在(.+?)存在组套重复收费，涉及(.+?)，总金额:(.+?)元', text)
    if m:
        return f'Charge item "{m.group(1)}" (code: {m.group(2)}) has package duplicate charge at {m.group(3)}, involving {m.group(4)}, total: {m.group(5)} yuan'
    # 收费项目"xxx"(代码:xxx)在N个组套中重复收费：xxx
    m = re.match(r'收费项目"(.+?)"\(代码:(.+?)\)在(.+?)个组套中重复收费：(.+)', text)
    if m:
        return f'Charge item "{m.group(1)}" (code: {m.group(2)}) has duplicate charges in {m.group(3)} packages: {m.group(4)}'
    # 父项目'xxx'(代码:xxx)与子项目'xxx'(代码:xxx)在xxx同时收费...
    m = re.match(r"父项目'(.+?)'\(代码:(.+?)\)与子项目'(.+?)'\(代码:(.+?)\)在(.+?)同时收费，疑似父子重复收费，涉及(.+?)，合计金额:(.+?)$", text)
    if m:
        return f'Parent item "{m.group(1)}" (code: {m.group(2)}) and child item "{m.group(3)}" (code: {m.group(4)}) charged simultaneously at {m.group(5)}, suspected parent-child duplicate, involving {m.group(6)}, total: {m.group(7)}'

    return text


def _system_issue(result: Optional[Result]) -> str:
    if not result:
        return ''
    raw = result.reason or result.violation_item or ''
    return _translate_reason(raw)


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
