"""医嘱频次规则的医嘱/收费双源证据工具。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List


# 收费项目代码与医嘱类别/项目代码的口径未证实一致，双源补充只按项目名称匹配。
_ORDER_EVENT_NAME_FIELDS = {"医嘱项目名称", "项目名称"}
_EMPTY_MARKERS = {"", "-", "none", "null", "nan", "xxx"}


class OrderChargeEvidenceList(list):
    """对现有规则兼容的医嘱/收费双源列表。

    普通代码仍把它当作医嘱列表使用；当经过 ``filter_list`` 按医嘱项目
    筛选时，会分别计算医嘱和收费两侧记录，并采用次数较大的一侧。
    """

    def __init__(self, orders: List[Dict], charge_events: List[Dict]):
        super().__init__(orders or [])
        self.order_events = list(orders or [])
        self.charge_events = list(charge_events or [])


def _text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in _EMPTY_MARKERS else text


def _number(value: Any):
    text = _text(value).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _is_valid_charge_time(value: Any) -> bool:
    """只把标准日期/时间作为频次时间证据，避免无效文本被误归为同日。"""
    text = _text(value)
    if not text:
        return False
    normalized = text.replace("Z", "+00:00")
    try:
        datetime.fromisoformat(normalized)
        return True
    except ValueError:
        try:
            datetime.strptime(text[:10], "%Y-%m-%d")
            return True
        except ValueError:
            return False


def _resolve_path(item: Any, path: str):
    current = item
    for key in (path or "").split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


def _filter_plain(data_list: List[Dict], field_path: str, match_value: Any, operator: str = "==") -> List[Dict]:
    if not data_list or not isinstance(data_list, list):
        return []

    result = []
    for item in data_list:
        actual_value = _resolve_path(item, field_path)
        if actual_value is None:
            continue

        is_hit = False
        actual_text = str(actual_value)
        try:
            if operator == "contains":
                if isinstance(match_value, list):
                    is_hit = any(str(keyword) in actual_text for keyword in match_value)
                else:
                    is_hit = str(match_value) in actual_text
            elif operator == "in":
                is_hit = actual_value in match_value
            elif operator == "==":
                is_hit = actual_text == str(match_value)
        except Exception:
            is_hit = False

        if is_hit:
            result.append(item)
    return result


def _deduplicate_events(events: List[Dict], source: str) -> List[Dict]:
    """按业务主键去掉同一侧重复入库的事件，保留出现顺序。

    医嘱优先用医嘱号/医嘱ID/处方号；收费优先用费用明细编号。主键缺失
    时保留原始行，避免把两个无法区分的真实事件误合并。
    """
    unique_events = []
    seen_keys = set()
    for index, item in enumerate(events or []):
        if not isinstance(item, dict):
            continue
        if source == "收费明细":
            business_key = _text(
                item.get("费用明细编号")
                or item.get("收费明细编号")
                or item.get("医嘱ID")
                or item.get("医嘱号")
            )
        else:
            business_key = _text(
                item.get("医嘱号")
                or item.get("医嘱ID")
                or item.get("处方号")
            )

        unique_key = f"{source}:{business_key}" if business_key else f"{source}:row:{index}"
        if unique_key in seen_keys:
            continue
        seen_keys.add(unique_key)
        unique_events.append(item)
    return unique_events


_GENERIC_CHARGE_SUMMARY_NAMES = {
    "西药费", "中成药", "中草药", "化验费", "检查费", "治疗费", "床费",
    "材料费", "诊察费", "手术费", "护理费", "麻醉费", "其他费", "药品费",
}


def _is_generic_charge_summary(name: str, category: str) -> bool:
    """识别与费用类别同名的汇总行，避免它覆盖真实项目明细。"""
    normalized_name = _text(name).replace(" ", "")
    normalized_category = _text(category).replace(" ", "")
    return bool(normalized_name) and (
        normalized_name in _GENERIC_CHARGE_SUMMARY_NAMES
        or (normalized_category and normalized_name == normalized_category)
    )


def _charge_detail_score(name: str, code: str, unit: str, category: str) -> int:
    """同一费用明细号存在汇总/明细两行时，为真实项目明细打更高分。"""
    if _is_generic_charge_summary(name, category):
        return -100
    score = 10
    if _text(code):
        score += 4
    if _text(unit):
        score += 2
    # 同类别的真实项目通常有更具体的名称；长度仅在其它信息相同时用于稳定择优。
    score += min(len(_text(name)), 50)
    return score


def _build_charge_order_events(patient_json: Dict) -> List[Dict]:
    """把有效收费明细投影成可用于医嘱频次核验的事件。

    一条收费明细只算一次收费事件，不能按项目数量展开；否则一次医嘱的多
    单位执行会被误判为多次开立。冲销/退费（数量或金额为负）不算正向证据。
    同一费用明细编号如同时出现费用类别汇总行和真实项目行，只保留真实项目行。
    """
    fees = patient_json.get("收费报告", []) if isinstance(patient_json, dict) else []
    if not isinstance(fees, list):
        return []

    best_events = {}
    for index, fee in enumerate(fees):
        if not isinstance(fee, dict):
            continue

        name = _text(fee.get("收费项目名称") or fee.get("项目名称"))
        code = _text(fee.get("收费项目代码") or fee.get("ORDER_ITEM_CODE") or fee.get("项目代码"))
        charge_time = _text(fee.get("收费日期") or fee.get("收费时间") or fee.get("记账时间"))
        category = _text(fee.get("费用类别"))
        unit = _text(fee.get("项目单位"))
        if not name or not _is_valid_charge_time(charge_time) or _is_generic_charge_summary(name, category):
            continue

        quantity = _number(fee.get("项目数量"))
        amount = _number(fee.get("项目费用") or fee.get("金额"))
        if quantity is not None and quantity <= 0:
            continue
        if amount is not None and amount < 0:
            continue

        detail_no = _text(fee.get("费用明细编号") or fee.get("收费明细编号"))
        # 有明确费用明细编号时按其去重；无编号时每一行都保留，避免吞掉
        # 同时发生的真实收费记录。
        unique_key = detail_no or "row:" + str(index)
        event_id = "收费明细:" + unique_key
        event = {
            "医嘱号": event_id,
            "医嘱ID": event_id,
            "医嘱项目名称": name,
            "医嘱项类别": code,
            "医嘱项目代码": code,
            "医嘱下达时间": charge_time,
            "医嘱开始时间": charge_time,
            "医嘱停止时间": charge_time,
            "收费日期": charge_time,
            "收费项目名称": name,
            "收费项目代码": code,
            "费用明细编号": detail_no,
            "收费报告索引": index,
            "证据来源": "收费明细",
            "时间来源": "收费日期",
        }
        score = _charge_detail_score(name, code, unit, category)
        previous = best_events.get(unique_key)
        # 分数相同时选择后出现的实际项目行：源数据常把汇总行排在前、明细行排在后。
        if previous is None or (score, index) >= (previous[0], previous[1]):
            best_events[unique_key] = (score, index, event)

    return [entry[2] for entry in sorted(best_events.values(), key=lambda entry: entry[1])]


def prepare_order_charge_evidence(patient_json: Dict) -> Dict[str, int]:
    """将病历中的医嘱替换为双源兼容列表，返回处理统计。

    原始医嘱不会删除，收费事件只在规则用 ``filter_list`` 筛选目标医嘱
    项目时参与次数比较。若两侧都有同一项目，取较大次数而不相加。
    """
    if not isinstance(patient_json, dict):
        return {"order_count": 0, "charge_event_count": 0}

    existing = patient_json.get("医嘱", [])
    if isinstance(existing, OrderChargeEvidenceList):
        return {
            "order_count": len(existing.order_events),
            "charge_event_count": len(existing.charge_events),
        }

    orders = existing if isinstance(existing, list) else []
    charge_events = _build_charge_order_events(patient_json)
    if charge_events:
        patient_json["医嘱"] = OrderChargeEvidenceList(orders, charge_events)
    return {"order_count": len(orders), "charge_event_count": len(charge_events)}


def is_order_event_field(field_path: str) -> bool:
    return field_path in _ORDER_EVENT_NAME_FIELDS


def filter_order_charge_evidence(
    data_list: OrderChargeEvidenceList,
    field_path: str,
    match_value: Any,
    operator: str = "==",
) -> List[Dict]:
    """返回医嘱/收费两源中目标项目记录数较多的一侧。"""
    order_items = _deduplicate_events(
        _filter_plain(data_list.order_events, field_path, match_value, operator), "医嘱"
    )
    charge_items = _deduplicate_events(
        _filter_plain(data_list.charge_events, field_path, match_value, operator), "收费明细"
    )
    return charge_items if len(charge_items) > len(order_items) else order_items


def get_order_frequency_evidence(
    ctx: Dict,
    target_value: Any,
    operator: str = "contains",
    field_path: str = "医嘱项目名称",
) -> Dict[str, Any]:
    """显式提供医嘱频次的双源统计，供新转换规则直接使用。"""
    order_list = ctx.get("医嘱", []) if isinstance(ctx, dict) else []
    if isinstance(order_list, OrderChargeEvidenceList):
        order_items = _deduplicate_events(
            _filter_plain(order_list.order_events, field_path, target_value, operator), "医嘱"
        )
        charge_items = _deduplicate_events(
            _filter_plain(order_list.charge_events, field_path, target_value, operator), "收费明细"
        )
    else:
        order_items = _deduplicate_events(
            _filter_plain(order_list, field_path, target_value, operator), "医嘱"
        )
        charge_items = []

    if len(charge_items) > len(order_items):
        effective_items = charge_items
        evidence_source = "收费明细"
    elif len(order_items) > len(charge_items):
        effective_items = order_items
        evidence_source = "医嘱"
    elif order_items and charge_items:
        effective_items = order_items
        evidence_source = "医嘱与收费明细（次数相同）"
    else:
        effective_items = []
        evidence_source = "无"

    return {
        "order_items": order_items,
        "charge_items": charge_items,
        "effective_items": effective_items,
        "order_count": len(order_items),
        "charge_count": len(charge_items),
        "effective_count": len(effective_items),
        "evidence_source": evidence_source,
    }
