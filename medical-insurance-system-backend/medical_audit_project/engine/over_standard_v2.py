import logging
import json
import re
from copy import deepcopy
from datetime import datetime
from dateutil import parser as date_parser
from typing import List, Dict, Any, Union
import requests
from pricings.models import StandardChargeItem
from rules.models import Rule  # 导入 Rule 模型
from engine.order_charge_evidence import (
    OrderChargeEvidenceList,
    filter_order_charge_evidence,
    get_order_frequency_evidence,
    is_order_event_field,
    prepare_order_charge_evidence,
)

logger = logging.getLogger(__name__)

# ==========================================
# L1 函数
# ==========================================
def _resolve_path(obj: Any, path: str, default: Any = None) -> Any:
    """辅助函数：根据 'a.b.c' 路径从字典中取值"""
    if not path:
        return obj
    
    current = obj
    for key in path.split('.'):
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return default
        
        if current is None:
            return default
            
    return current

def get_val(source: Union[Dict, List, Any], path: str, default: Any = None) -> Any:
    """
    通用数据提取器 (增强版)。
    核心能力：
    1. 字典深度访问: "a.b.c"
    2. 列表自动穿透 (Auto-Projection): 
       如果在路径遍历中遇到列表，会自动将剩余路径应用到列表中的每一项，
       并返回扁平化的结果列表。
    """
    if source is None:
        return default
        
    if not path:
        return source

    keys = path.split('.')
    current = source
    
    for i, key in enumerate(keys):
        # 1. 当前是字典：正常下钻
        if isinstance(current, dict):
            current = current.get(key)
            if current is None:
                return default
        
        # 2. 当前是列表：触发“自动穿透”模式
        elif isinstance(current, list):
            # 说明路径还没走完就遇到了列表
            # 我们需要把剩余的路径 (包括当前这个key) 应用到列表里的每个元素上
            remaining_path = ".".join(keys[i:])
            
            results = []
            for item in current:
                # 递归提取
                val = get_val(item, remaining_path)
                
                # 收集结果 (自动扁平化处理)
                if val is not None and val != []:
                    if isinstance(val, list):
                        results.extend(val) # 已经是列表了，铺平加入
                    else:
                        results.append(val)
            
            return results if results else default
            
        # 3. 当前是基础值但路径还没结束：死路
        else:
            return default

    return current

def filter_list(
    data_list: List[Dict],
    field_path: str,
    match_value: Any,
    operator: str = "==",
    include_charge_frequency: bool = False,
) -> List[Dict]:
    if (
        include_charge_frequency
        and isinstance(data_list, OrderChargeEvidenceList)
        and is_order_event_field(field_path)
    ):
        # 医嘱、收费分别计数，取较大值；不把同一医疗行为的两份记录相加。
        return filter_order_charge_evidence(data_list, field_path, match_value, operator)

    if not data_list or not isinstance(data_list, list):
        return []

    result = []
    for item in data_list:
        actual_value = _resolve_path(item, field_path)
        if actual_value is None:
            continue

        is_hit = False
        str_actual = str(actual_value) # 预先转字符串

        try:
            # ==========================================
            # 1. Contains (支持 单个字符串 或 字符串列表)
            # ==========================================
            if operator == "contains":
                if isinstance(match_value, list):
                    # 【核心修正】你的需求：批量模糊匹配
                    # 逻辑：遍历关键词列表，看 actual 是否包含其中任意一个
                    for keyword in match_value:
                        if str(keyword) in str_actual:
                            is_hit = True
                            break # 只要命中一个，就停止循环
                else:
                    # 原逻辑：单值模糊匹配
                    is_hit = str(match_value) in str_actual

            # ==========================================
            # 2. In (保持 SQL 语义：精确匹配白名单)
            # ==========================================
            elif operator == "in":
                # 场景：筛选科室 ["内科", "外科"]
                # 逻辑：actual 必须完全等于列表中的某一项
                is_hit = actual_value in match_value

            # ... 其他操作符 (==, >, <) 保持不变 ...
            elif operator == "==":
                is_hit = str_actual == str(match_value)
            # ...

        except Exception:
            is_hit = False

        if is_hit:
            result.append(item)

    return result

def calc_stats(data_list: List[Any], method: str) -> Any:
    """
    对纯值列表进行计算。
    支持：sum, count, avg, max, min, max_gap, min_gap, span_days
    """
    if not data_list:
        return 0 if method in ["count", "sum"] else None

    # 基础数学统计
    if method == "count": return len(data_list)
    if method == "sum": return sum([float(x) for x in data_list if x is not None])
    if method == "avg": return sum([float(x) for x in data_list]) / len(data_list)
    if method == "max": return max(data_list)
    if method == "min": return min(data_list)
    if method == "distinct_count": return len(set(data_list))

    # 日期特殊计算
    if method in ["max_gap", "min_gap", "span_days"]:
        try:
            # 1. 转换并排序
            dates = sorted([date_parser.parse(str(d)) for d in data_list if d])
            if len(dates) < 2:
                return 0
            
            # 2. span_days: 计算最早到最晚日期的总跨度
            if method == "span_days":
                return (dates[-1] - dates[0]).days
            
            # 3. 计算相邻差值
            diffs = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
            
            if method == "max_gap": return max(diffs)
            if method == "min_gap": return min(diffs)
            
        except Exception as e:
            print(f"Date Calc Error: {e}")
            return 0

    return None

# ==========================================
# L2 函数
# ==========================================
def list_contains(target_list: List[Any], keyword: str) -> bool:

    if not target_list:
        return False
    
    str_list = [str(x) for x in target_list if x]
    
    for item in str_list:
        if keyword in item: 
            return True
            
    return False

def is_compare(value: float, operator: str, threshold: float) -> bool:
    """数值比较"""
    try:
        val = float(value)
        th = float(threshold)
        
        if operator == ">": return val > th
        if operator == ">=": return val >= th
        if operator == "<": return val < th
        if operator == "<=": return val <= th
        if operator == "==": return val == th
        if operator == "!=": return val != th
    except:
        return False
    return False

# 与 data_adapter.sy 中的 qwen_legacy 配置一致；compose 使用 host 网络，
# 因此此处访问的就是宿主机实际监听的模型端口。
RULE_LLM_URL = "http://127.0.0.1:54320/v1/chat/completions"
RULE_LLM_MODEL = "qwen3-30b-a3b"


def _parse_llm_boolean(answer: str) -> bool:
    """仅接受明确的肯定回答，避免把“不是”误判成“是”。"""
    normalized = (answer or "").strip().lower()
    first_line = normalized.splitlines()[0].strip(" \t\r\n。！!，,；;") if normalized else ""
    if first_line in {"是", "yes", "true"}:
        return True
    if first_line in {"否", "不是", "no", "false"}:
        return False
    logger.warning("LLM回答不符合是/否约束，按否处理：%s", answer)
    return False


def llm_bool(context_text: str, question: str) -> bool:
    """调用已部署的病历抽取模型，返回其明确的“是/否”判断。"""
    if not context_text or len(context_text) < 2:
        return False

    prompt = (
        "请根据以下病历信息回答问题。只能输出一个字：是 或 否；"
        "不得输出分析、解释或其他文字。\n\n"
        f"病历信息：{context_text}\n\n问题：{question}\n\n回答："
    )
    logger.info("--- [LLM CALL] ---\nEndpoint: %s\nContext: %s...\nQ: %s", RULE_LLM_URL, context_text[:200], question)

    try:
        payload = {
            "model": RULE_LLM_MODEL,
            "messages": [
                {"role": "system", "content": "你是医学规则判定器。禁止输出思考过程、分析或解释；只能输出一个字：是或否。"},
                {"role": "user", "content": prompt},
            ],
            # Qwen3 默认可能先输出推理过程；vLLM 的此参数会关闭思考模式，
            # 以便模型在有限输出内直接给出可机器判读的“是/否”。
            "chat_template_kwargs": {"enable_thinking": False},
            "temperature": 0.1,
            "max_tokens": 8,
        }
        response = requests.post(RULE_LLM_URL, json=payload, timeout=15)
        response.raise_for_status()
        result = response.json()
        answer = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        logger.info("--- [LLM RESPONSE] ---\nEndpoint: %s\nAnswer: %s", RULE_LLM_URL, answer)
        return _parse_llm_boolean(answer)
    except Exception as exc:
        logger.error("LLM调用错误: %s", exc)
        return False

# ==========================================
# Interface 
# ==========================================
def submit_result(is_applicable: bool, is_compliant: bool = True, failure_message: str = "", evidence: Dict = None):
    """
    标准化返回结果封装
    """
    return {
        "is_applicable": is_applicable,  # 是否入组/适用
        "is_compliant": is_compliant,    # 是否合规
        "failure_message": failure_message if not is_compliant else "通过",
        "evidence": evidence or {}       # 审计证据链
    }


# 收费项目名称和代码必须来自病历中的 ``收费报告``，不能用规则配置字段代替。
# 规则配置只可用来定位候选条目；最终返回值始终是原始收费条目的快照。
_CHARGE_NAME_KEYS = {
    "收费项目名称", "项目名称", "项目名", "药品名称", "药品通用名",
    "name", "item_name", "drug_name",
}
_CHARGE_CODE_KEYS = {
    "收费项目代码", "项目代码", "收费编码", "医保编码",
    "code", "item_code", "drug_code",
}


def _non_empty_text(value: Any) -> str:
    """将病历字段标准化为可比较的字符串；空值不参与匹配。"""
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"", "none", "null", "xxx"} else text


def _collect_charge_clues(value: Any, names: set, codes: set, indexes: set) -> None:
    """从规则证据链中提取收费项目线索和明确的收费报告索引。"""
    if isinstance(value, dict):
        field_path = value.get("field_path")
        if isinstance(field_path, str):
            indexes.update(int(index) for index in re.findall(r"收费报告\[(\d+)\]", field_path))

        for key, item_value in value.items():
            text = _non_empty_text(item_value)
            if key in _CHARGE_NAME_KEYS and text:
                names.add(text)
            elif key in _CHARGE_CODE_KEYS and text:
                codes.add(text)

        # 高亮文本本身没有字段名时，用其与收费项目名称/代码精确比对。
        highlighted_text = _non_empty_text(value.get("highlighted_text"))
        if highlighted_text:
            names.add(highlighted_text)
            codes.add(highlighted_text)

        for item_value in value.values():
            _collect_charge_clues(item_value, names, codes, indexes)
    elif isinstance(value, list):
        for item in value:
            _collect_charge_clues(item, names, codes, indexes)


def get_matched_charge_items(patient_json: Dict, rule: Rule, evidence: Dict = None) -> List[Dict]:
    """
    从原始收费报告中返回规则实际命中的收费条目。

    返回的每一条都保留原始字段，并增加 ``收费明细索引`` 方便前端精确定位。
    证据不足时可用规则的精确匹配条件定位，但返回值仍只能是原始收费条目，
    绝不直接把规则名称或匹配值伪装成收费项目名称/代码。
    """
    fee_data = patient_json.get("收费报告", []) if isinstance(patient_json, dict) else []
    if not isinstance(fee_data, list):
        return []

    names, codes, indexes = set(), set(), set()
    _collect_charge_clues(evidence or {}, names, codes, indexes)

    # 规则的匹配条件是最后的定位回退，仅做精确匹配，避免把相似项目误标为违规。
    match_field = _non_empty_text(getattr(rule, "match_field", ""))
    match_value = _non_empty_text(getattr(rule, "match_value", ""))
    rule_name = _non_empty_text(getattr(rule, "drug_name", ""))

    matched = []
    seen_indexes = set()
    for index, raw_item in enumerate(fee_data):
        if not isinstance(raw_item, dict):
            continue

        item_name = _non_empty_text(raw_item.get("收费项目名称"))
        item_code = _non_empty_text(raw_item.get("收费项目代码"))
        if not item_name or not item_code:
            # 源数据本身缺少名称或代码时不能补造，避免输出不准确的数据。
            continue

        evidence_hit = (
            index in indexes
            or item_name in names
            or item_code in codes
        )
        # 优先使用规则证据链定位原始条目。
        if evidence_hit and index not in seen_indexes:
            snapshot = deepcopy(raw_item)
            snapshot.pop("_index", None)  # 检测器运行时的临时字段不写入结果
            snapshot["收费明细索引"] = index
            matched.append(snapshot)
            seen_indexes.add(index)

    # 证据可能只含价格、诊断等非项目字段。此时才回退到规则的精确匹配条件；
    # 仍然只返回收费报告中的真实条目，绝不直接返回配置值。
    if not matched:
        for index, raw_item in enumerate(fee_data):
            if not isinstance(raw_item, dict):
                continue
            item_name = _non_empty_text(raw_item.get("收费项目名称"))
            item_code = _non_empty_text(raw_item.get("收费项目代码"))
            rule_match = (
                bool(match_field and match_value and _non_empty_text(raw_item.get(match_field)) == match_value)
                or bool(rule_name and item_name == rule_name)
            )
            if item_name and item_code and rule_match:
                snapshot = deepcopy(raw_item)
                snapshot.pop("_index", None)
                snapshot["收费明细索引"] = index
                matched.append(snapshot)

    return matched


def build_charge_violation_item(patient_json: Dict, rule: Rule, rule_type: str, evidence: Dict = None) -> Dict:
    """构造结果中的收费项目快照，名称和代码只取自实际收费明细。"""
    details = get_matched_charge_items(patient_json, rule, evidence)
    if details:
        first_item = details[0]
        return {
            "收费项目名称": first_item["收费项目名称"],
            "收费项目代码": first_item["收费项目代码"],
            "收费明细": details,
            "提示": f"违反{rule_type}规则",
        }

    return {
        "收费项目名称": "",
        "收费项目代码": "",
        "收费明细": [],
        "提示": f"违反{rule_type}规则；未定位到可对应的原始收费明细",
    }


def build_charge_highlights(details: List[Dict], evidence: Dict = None) -> List[Dict]:
    """保留规则证据，并补充每条已定位收费明细的精确名称、代码高亮。"""
    highlights = []
    seen = set()
    for item in (evidence or {}).get("highlights", []):
        if not isinstance(item, dict):
            continue
        field_path = _non_empty_text(item.get("field_path"))
        text = _non_empty_text(item.get("highlighted_text"))
        if field_path and text and (field_path, text) not in seen:
            highlights.append({"field_path": field_path, "highlighted_text": text})
            seen.add((field_path, text))

    for item in details:
        index = item.get("收费明细索引")
        for field in ("收费项目名称", "收费项目代码"):
            text = _non_empty_text(item.get(field))
            field_path = f"$.收费报告[{index}].{field}"
            if text and (field_path, text) not in seen:
                highlights.append({"field_path": field_path, "highlighted_text": text})
                seen.add((field_path, text))
    return highlights


def preprocess_patient_data(patient_json: dict):
    """
    数据适配层：
    1. 扁平化 '用药信息'：如果它是字典（含治疗用药/手术用药），则合并为列表。
    2. 字段映射：将 '药物名称' 复制一份给 '药品通用名'，以兼容规则代码。
    
    注意：此操作会修改传入的 patient_json 对象（引用传递）。
    """
    try:
        med_info = patient_json.get("用药信息")
        
        # 1. 扁平化处理
        flat_med_list = []
        if isinstance(med_info, dict):
            # 提取所有子列表（如 "治疗用药", "手术用药"）
            for key, val in med_info.items():
                if isinstance(val, list):
                    flat_med_list.extend(val)
            
            logger.info(f"[Preprocess] Detected dict-type '用药信息', flattened into {len(flat_med_list)} items.")
            
            # 将扁平化后的列表回写到 ctx，以便 get_val(ctx, "用药信息") 能拿到列表
            # 注意：这改变了数据结构，但对于只读规则是安全的
            patient_json["用药信息"] = flat_med_list
            
        elif isinstance(med_info, list):
            flat_med_list = med_info
        else:
            # 如果不存在或格式不对，尝试从收费报告中提取药品作为兜底（可选）
            # 目前只处理存在的情况
            flat_med_list = []

        # 2. 字段映射处理
        mapped_count = 0
        for item in flat_med_list:
            if isinstance(item, dict):
                # 规则代码常查找 "药品通用名"，而数据中可能是 "药物名称"
                if "药品通用名" not in item and "药物名称" in item:
                    item["药品通用名"] = item["药物名称"]
                    mapped_count += 1
        
        if mapped_count > 0:
            logger.info(f"[Preprocess] Mapped '药物名称' to '药品通用名' for {mapped_count} items.")

        # 医嘱频次规则需要同时参考收费明细。两侧后续在 filter_list 中分别
        # 去重计数并取较大值，避免医嘱和收费的同一行为被重复相加。
        order_charge_stats = prepare_order_charge_evidence(patient_json)
        if order_charge_stats["charge_event_count"]:
            logger.info(
                "[Preprocess] Prepared order/charge frequency evidence: orders=%s, charge_events=%s.",
                order_charge_stats["order_count"],
                order_charge_stats["charge_event_count"],
            )
            
    except Exception as e:
        logger.error(f"[Preprocess] Error during data preprocessing: {e}", exc_info=True)


def _is_order_frequency_rule(rule: Rule) -> bool:
    """判断规则是否允许用收费次数补充医嘱频次。

    收费时间不是开嘱时间，因此“同时开具”只能依据真实医嘱时间，绝不以收费
    时间推断；同一次住院/同日/短期重复/次数上限等频次规则才允许收费补证。
    """
    rule_text = " ".join(
        str(value or "")
        for value in (getattr(rule, "drug_name", ""), getattr(rule, "description", ""), getattr(rule, "rule_code", ""))
    )
    has_order_context = "医嘱" in rule_text or "开立" in rule_text
    if not has_order_context:
        return False
    if any(token in rule_text for token in ("同时开具", "同时开立", "同时下达")):
        return False
    frequency_tokens = ("不超过", "超过", "次数", "频次", "重复", "同一次住院", "同一日", "短期")
    return any(token in rule_text for token in frequency_tokens)


def _make_rule_filter_list(include_charge_frequency: bool):
    """为当前规则绑定收费频次开关，避免同一执行批次规则相互污染。"""
    def _rule_filter_list(data_list, field_path, match_value, operator="=="):
        return filter_list(
            data_list,
            field_path,
            match_value,
            operator,
            include_charge_frequency=include_charge_frequency,
        )
    return _rule_filter_list


def _upgrade_legacy_short_order_rule_code(rule_code: str) -> str:
    """让已入库的旧版“短期内重复开具医嘱”规则也使用双源次数证据。

    旧模板在定义 ``target_aliases`` 后直接遍历 ``get_val(ctx, "医嘱")``。
    这里仅替换该固定模板的取数行，先按别名比较医嘱/收费两侧次数，取较大
    的事件列表；其他规则代码保持原样。
    """
    if not isinstance(rule_code, str) or "target_aliases" not in rule_code or "short_period_days" not in rule_code:
        return rule_code

    pattern = r'(?m)^(\s*)orders\s*=\s*get_val\(ctx,\s*["\']医嘱["\'],\s*default\s*=\s*\[\]\s*\)\s*$'
    replacement = (
        r'\1frequency_evidence = get_order_frequency_evidence(ctx, target_aliases, "contains")\n'
        r'\1orders = frequency_evidence["effective_items"]'
    )
    upgraded, count = re.subn(pattern, replacement, rule_code, count=1)
    if count:
        # 同时把双来源统计写入旧规则的两个返回证据字典，使历史已入库规则
        # 无需重新保存也能展示医嘱/收费的分别计数。
        evidence_pattern = r'(?m)^(\s*)"short_period_days": short_period_days,'
        evidence_replacement = (
            r'\1"short_period_days": short_period_days,\n'
            r'\1"医嘱匹配数": frequency_evidence["order_count"],\n'
            r'\1"收费匹配数": frequency_evidence["charge_count"],\n'
            r'\1"有效次数": frequency_evidence["effective_count"],\n'
            r'\1"次数核验来源": frequency_evidence["evidence_source"],'
        )
        upgraded = re.sub(evidence_pattern, evidence_replacement, upgraded)
        logger.info("[RuleEngineV2] Applied order/charge frequency compatibility to legacy short-period rule.")
    return upgraded


def check_indication_rule(patient_json: dict, target_rules=None) -> list:
    """
    Wrapper for execute_db_rules to maintain compatibility.
    Targeting '超限定用药' rules.
    """
    return execute_db_rules(patient_json, rule_type='超限定用药', target_rules=target_rules)

def execute_db_rules(patient_json: dict, rule_type: str, target_rules=None) -> list:

    logger.info(f"[RuleEngineV2] Starting check for type='{rule_type}'...")
    

    preprocess_patient_data(patient_json)
    

    if target_rules is not None:
        # 只要调用方显式传入了 target_rules，就严格以它为准；空列表表示
        # “本任务未选择此类规则”，不能回退为执行规则库中的全部启用规则。
        # 需确保只执行属于当前 rule_type 的规则，防止规则混用
        all_target_rules = target_rules
        rules = [r for r in all_target_rules if r.type == rule_type]
        logger.info(f"[RuleEngineV2] Using {len(rules)} provided target rules (filtered from {len(all_target_rules)} total).")
    else:
        # 否则，从数据库查询
        rules = Rule.objects.filter(type=rule_type, status=True)
        if not rules.exists():
            logger.warning(f"[RuleEngineV2] No active rules found with type='{rule_type}'.")
            return []
        logger.info(f"[RuleEngineV2] Loaded {rules.count()} rules from DB.")
    
    all_results = []
    ctx = patient_json
    

    exec_globals = {
        'get_val': get_val,
        'filter_list': filter_list,
        'calc_stats': calc_stats, # 新增 calc_stats
        'list_contains': list_contains,
        'is_compare': is_compare, # Added for Price Check logic
        'llm_bool': llm_bool,
        'get_order_frequency_evidence': get_order_frequency_evidence,
        'submit_result': submit_result,
        'json': json,
        're': re,
        'logger': logger,
        'print': print, # Optional: for debugging
    }
    

    for rule in rules:
        if not rule.rule_code or not rule.rule_code.strip():
            logger.warning(f"Rule {rule.rule_id} has no code. Skipping.")
            continue
            
        try:
            logger.info(f"Executing rule: {rule.rule_id} ({rule.drug_name})")
            

            exec_globals['match_value'] = rule.drug_name
            exec_globals['drug_name'] = rule.drug_name
            exec_globals['rule_id'] = rule.rule_id
            use_charge_frequency = _is_order_frequency_rule(rule)
            exec_globals['filter_list'] = _make_rule_filter_list(use_charge_frequency)
            if use_charge_frequency:
                logger.info("[RuleEngineV2] Charge evidence enabled for order-frequency rule %s.", rule.rule_id)

            exec_locals = {}
            

            runtime_rule_code = _upgrade_legacy_short_order_rule_code(rule.rule_code)
            exec(runtime_rule_code, exec_globals, exec_locals)
            
            execute_func = exec_locals.get('execute_rule')
            
            if not execute_func or not callable(execute_func):
                logger.error(f"Rule {rule.rule_id} does not define 'execute_rule(ctx)'.")
                continue

            res = execute_func(ctx)

            if not res.get('is_applicable', False):
                continue
                
            if not res.get('is_compliant', True):
                logger.info(f"[RuleEngineV2] Violation found for rule {rule.rule_id}")

                evidence = res.get("evidence", {})
                violation_item = build_charge_violation_item(
                    patient_json=patient_json,
                    rule=rule,
                    rule_type=rule_type,
                    evidence=evidence,
                )
                highlights = build_charge_highlights(
                    violation_item["收费明细"], evidence
                )
                
                all_results.append({
                    "passed": False,
                    "reason": res.get('failure_message', f'违反{rule_type}规则'),
                    "ruleId": rule.rule_id,
                    "item": violation_item,
                    "highlights": highlights,
                    "violation": True,
                    "rule": {
                        "rule_id": rule.rule_id,
                        "drug_name": rule.drug_name,
                        "description": rule.description,
                        "type": rule.type
                    }
                })
            else:
                logger.info(f"Rule {rule.rule_id} passed.")
                
        except Exception as e:
            logger.error(f"Error executing rule {rule.rule_id}: {e}", exc_info=True)
            
    return all_results

# ==========================================
# 旧逻辑: 收费检查 (超标准收费)
# ==========================================
UNIT_EQUIVALENCE = {
    "例": ["例", "项", "次"],
    "项": ["例", "项", "次"],
    "次": ["例", "项", "次","片"],
    "日": ["日", "天"],
    "天": ["日", "天"],
}

def is_unit_equivalent(unit1, unit2, describe, name):
    if not unit1 or not unit2: return False
    unit1, unit2 = str(unit1), str(unit2)
    if unit1 == unit2: return True
    for equivalents in UNIT_EQUIVALENCE.values():
        if unit1 in equivalents and unit2 in equivalents:
            return True
    if "每种" in unit2 or "两根" in unit2: return True
    if unit2.startswith("每个") and unit2 != "每个部位": return True
    if unit1 in unit2 or unit2 in unit1: return True
    if unit2 in ("每个部位", "部位"):
        brackets = re.findall(r'\((.*?)\)', name)
        if not brackets: return False
        return any(
            (buwei in str(describe)) or (buwei.strip() == "其他")
            for buwei in brackets
        )
    return False

def check_over_standard(patient_json: dict) -> list:
    """
    Original Price Check Logic.
    """
    fee_data = patient_json.get("收费报告", [])
    if not fee_data:
        return []

    results = []
    target_date = datetime.strptime("2025-02-15", "%Y-%m-%d")

    charge_codes = [item.get('收费项目代码') for item in fee_data if item.get('收费项目代码')]
    if not charge_codes:
        return []
        
    standard_items_qs = StandardChargeItem.objects.filter(charge_code__in=charge_codes)
    standard_items_map = {item.charge_code: item for item in standard_items_qs}

    for index, charge_item in enumerate(fee_data):
        charge_code = charge_item.get('收费项目代码')
        charge_name = charge_item.get('收费项目名称', '未知名称')
        standard_item_obj = standard_items_map.get(charge_code)

        if not standard_item_obj: continue
        if str(standard_item_obj.insurance_code)[:2]!="00": continue
        if "床位费" in charge_name: continue

        try:
            charge_date_str = charge_item.get("收费日期")
            if not charge_date_str: continue
            charge_date = datetime.strptime(charge_date_str, "%Y-%m-%d %H:%M:%S")
            current_price_str = charge_item.get("项目单价")
            if current_price_str is None: continue
            current_price = float(current_price_str)
        except Exception:
            continue

        standard_price = standard_item_obj.price_2024 if charge_date >= target_date else (standard_item_obj.price_2021 or standard_item_obj.price_2024)
        if standard_price is None: continue
        
        standard_price_float = float(standard_price)
        price_check = current_price <= standard_price_float
        
        text = standard_item_obj.description_2024 if charge_date >= target_date else standard_item_obj.description_2021
        unit_check = is_unit_equivalent(charge_item.get("项目单位"), standard_item_obj.unit, str(text), charge_name)
        
        if not price_check or not unit_check:
            basis = f"{charge_name}收费单位应为{standard_item_obj.unit}, 收费单价应为{str(standard_price_float)}"
            reason = ""
            highlights = []

            if not price_check:
                reason += f"价格超标:标准价{str(standard_price_float)},实际价{current_price}。"
                highlights.append({
                    "field_path": f"$.收费报告[{index}].项目单价",
                    "highlighted_text": str(current_price)
                })

            if not unit_check:
                reason += f"单位不符:标准'{standard_item_obj.unit}',实际'{charge_item.get('项目单位')}'。"
                highlights.append({
                    "field_path": f"$.收费报告[{index}].项目单位",
                    "highlighted_text": str(charge_item.get("项目单位"))
                })
            
            results.append({
                "violation": True,
                "item": charge_item,
                "reason": reason.strip(),
                "rule": {
                    "rule_id": f"OVER_STANDARD_{standard_item_obj.charge_code}",
                    "drug_name": charge_name,
                    "description": basis,
                    "type": "超标准收费"
                },
                "highlights": highlights
            })
    return results
