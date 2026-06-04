from datetime import datetime
import re
from pricings.models import StandardChargeItem
import logging

logger = logging.getLogger(__name__)

# --- 单位换算逻辑保持不变 ---
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

# --- 带有诊断日志的核心函数 ---
def check_over_standard(patient_json: dict) -> list:
    """
    接收一个病历JSON，与数据库中的标准价目表进行比对，
    返回一个包含高亮信息的超标准违规结果列表。
    """
    fee_data = patient_json.get("收费报告", [])
    if not fee_data:
        logger.warning("[OverStandard] 病历JSON中未找到 '收费报告' 或其内容为空。")
        return []

    results = []
    target_date = datetime.strptime("2025-02-15", "%Y-%m-%d")

    charge_codes = [item.get('收费项目代码') for item in fee_data if item.get('收费项目代码')]
    if not charge_codes:
        logger.warning("[OverStandard] '收费报告' 中没有任何项目包含 '收费项目代码'。")
        return []
        
    standard_items_qs = StandardChargeItem.objects.filter(charge_code__in=charge_codes)
    standard_items_map = {item.charge_code: item for item in standard_items_qs}

    for index, charge_item in enumerate(fee_data):
        charge_code = charge_item.get('收费项目代码')
        charge_name = charge_item.get('收费项目名称', '未知名称')
        
        # --- 侦探日志 1: 开始检查 ---
        logger.info(f"[OverStandard] 正在检查项目: '{charge_name}' (代码: {charge_code})")

        standard_item_obj = standard_items_map.get(charge_code)

        if not standard_item_obj:
            logger.info(f"  -> 跳过原因: 在数据库中未找到此收费代码对应的标准价目。")
            continue
        # --- 【把新的日志行粘贴在这里】 ---
        # 就在 if not standard_item_obj: 判断之后，下一个 if 判断之前
        logger.info(f"  -> [深度诊断] 查找到的标准项: code='{standard_item_obj.charge_code}', name='{standard_item_obj.item_name}', price2024='{standard_item_obj.price_2024}', price2021='{standard_item_obj.price_2021}', unit='{standard_item_obj.unit}'")
        if str(standard_item_obj.insurance_code)[:2]!="00":
             logger.info(f"  -> 跳过原因: 医保编码 '{standard_item_obj.insurance_code}' 不是00开头。")
             continue
        if "床位费" in charge_name:
             logger.info(f"  -> 跳过原因: 项目名称包含'床位费'。")
             continue

        try:
            charge_date_str = charge_item.get("收费日期")
            if not charge_date_str: 
                logger.warning(f"  -> 跳过原因: '收费日期' 字段为空或不存在。")
                continue
            charge_date = datetime.strptime(charge_date_str, "%Y-%m-%d %H:%M:%S")
            current_price_str = charge_item.get("项目单价")
            if current_price_str is None:
                logger.warning(f"  -> 跳过原因: '项目单价' 字段为空或不存在。")
                continue
            current_price = float(current_price_str)
        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"  -> 跳过原因: 解析收费日期或单价失败 - {e}")
            continue

        standard_price = standard_item_obj.price_2024 if charge_date >= target_date else (standard_item_obj.price_2021 or standard_item_obj.price_2024)
        
        if standard_price is None:
            logger.warning(f"  -> 跳过原因: 数据库中此项目的标准价格为空。")
            continue
        
        standard_price_float = float(standard_price)
        price_check = current_price <= standard_price_float
        
        text = standard_item_obj.description_2024 if charge_date >= target_date else standard_item_obj.description_2021
        unit_check = is_unit_equivalent(charge_item.get("项目单位"), standard_item_obj.unit, str(text), charge_name)
        
        # --- 侦探日志 2: 打印对比结果 ---
        logger.info(f"  -> 对比结果: 标准价={standard_price_float}, 实际价={current_price} (价格检查通过: {price_check})")
        logger.info(f"  -> 对比结果: 标准单位='{standard_item_obj.unit}', 实际单位='{charge_item.get('项目单位')}' (单位检查通过: {unit_check})")
        
        if not price_check or not unit_check:
            logger.info(f"  => 发现违规！正在生成结果...")
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
        else:
            logger.info(f"  -> 检查通过，无违规。")
    
    logger.info(f"[OverStandard] 检查完成，共发现 {len(results)} 条超标准收费违规。")
    return results