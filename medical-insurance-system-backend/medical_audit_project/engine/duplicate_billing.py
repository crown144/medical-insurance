from datetime import datetime
import logging
import json
import re
from typing import List, Dict, Any, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

# DeepSeek API配置 - 注释掉，待服务器部署后启用
# DEEPSEEK_CONFIG = {
#     "deepseek-r1": {
#         'api_key': 'sk-87a571f6553c48b2ad4ed94356be4c11',
#         'api_base': 'http://10.130.252.83:1025/v1',
#         'model_name': 'DeepSeek-R1',
#     }
# }

def detect_duplicate_charges(patient_json: dict) -> list:
    """
    检测重复收费违规（符合925标准）
    接收一个病历JSON，检测其中的组套重复收费项目，
    返回一个包含高亮信息的重复收费违规结果列表。
    
    925标准：只有当同一收费项目代码对应多个不同的ORDER_ITEM_CODE时才算违规
    """
    fee_data = patient_json.get("收费报告", [])
    if not fee_data:
        logger.warning("[DuplicateBilling] 病历JSON中未找到 '收费报告' 或其内容为空。")
        return []

    results = []
    
    # 按时间分组收费项目（925标准逻辑）
    time_groups = defaultdict(list)
    for index, charge in enumerate(fee_data):
        # 跳过ORDER_ITEM_CODE为"xxx"的记录
        order_item_code = charge.get("ORDER_ITEM_CODE", "")
        if order_item_code == "xxx":
            continue

        charge_date = charge.get("收费日期", "")
        if charge_date:
            # 提取日期部分作为时间批次
            date_part = charge_date.split(' ')[0] if ' ' in charge_date else charge_date
            charge['_index'] = index  # 保存原始索引用于高亮
            time_groups[date_part].append(charge)

    # 检查每个时间批次中的重复收费
    for charge_time, charges in time_groups.items():
        # 按收费项目代码分组
        code_groups = defaultdict(list)
        for charge in charges:
            charge_code = charge.get("收费项目代码", "")
            if charge_code:
                code_groups[charge_code].append(charge)

        # 检测组套重复收费
        for charge_code, same_code_charges in code_groups.items():
            if len(same_code_charges) > 1:
                # 检查是否有多个不同的ORDER_ITEM_CODE
                order_item_codes = set()
                for charge in same_code_charges:
                    order_code = charge.get("ORDER_ITEM_CODE", "")
                    if order_code and order_code != "xxx":
                        order_item_codes.add(order_code)
                
                # 只有当存在多个不同的ORDER_ITEM_CODE时才认为是违规
                if len(order_item_codes) > 1:
                    charge_name = same_code_charges[0].get("收费项目名称", "未知名称")
                    
                    logger.info(f"[DuplicateBilling] 发现组套重复收费: {charge_name} (代码: {charge_code}) 在 {charge_time} 有 {len(order_item_codes)} 个不同组套")
                    
                    # 计算总金额
                    total_amount = 0
                    duplicate_items = []
                    highlights = []
                    
                    for charge in same_code_charges:
                        try:
                            unit_price = float(charge.get('项目单价', 0))
                            quantity = float(charge.get('数量', 1))
                            amount = unit_price * quantity
                            total_amount += amount
                            
                            duplicate_items.append({
                                '收费项目代码': charge.get('收费项目代码'),
                                '收费项目名称': charge.get('收费项目名称'),
                                '收费日期': charge.get('收费日期'),
                                'ORDER_ITEM_CODE': charge.get('ORDER_ITEM_CODE'),
                                '项目单价': charge.get('项目单价'),
                                '数量': charge.get('数量'),
                                '金额': amount
                            })
                            
                            # 添加高亮信息
                            highlights.append({
                                'field_path': f'收费报告[{charge.get("_index", 0)}]',
                                'highlighted_text': f'{charge_name} - {charge.get("收费日期")} - ORDER_ITEM_CODE:{charge.get("ORDER_ITEM_CODE")}'
                            })
                            
                        except (ValueError, TypeError) as e:
                            logger.warning(f"[DuplicateBilling] 计算金额失败: {e}")
                            continue
                    
                    # 构建违规结果
                    violation_result = {
                        'violation': True,
                        'rule': {
                            'rule_id': f'DUPLICATE_BILLING_925_{charge_code}',
                            'type': '重复收费-组套',
                            'drug_name': charge_name,
                            'description': f'检测到同一收费项目在不同组套中重复收费（符合925标准）'
                        },
                        'reason': f'收费项目"{charge_name}"(代码:{charge_code})在{charge_time}存在组套重复收费，涉及{len(order_item_codes)}个不同组套，总金额:{total_amount:.2f}元',
                        'item': {
                            '收费项目代码': charge_code,
                            '收费项目名称': charge_name,
                            '重复日期': charge_time,
                            '组套数量': len(order_item_codes),
                            '重复次数': len(same_code_charges),
                            '总金额': total_amount,
                            '明细': duplicate_items
                        },
                        'highlights': highlights
                    }
                    
                    results.append(violation_result)
    
    logger.info(f"[DuplicateBilling] 重复收费检测完成（925标准），发现 {len(results)} 项违规")
    return results


def check_duplicate_billing_advanced(patient_json: dict) -> list:
    """
    高级重复收费检测（可扩展用于AI分析）
    """
    # 基础检测
    basic_results = detect_duplicate_charges(patient_json)
    
    # TODO: 这里可以集成AI分析逻辑
    # 当DeepSeek API配置启用时，可以进行更复杂的重复收费模式识别
    
    return basic_results


def analyze_billing_patterns(fee_data: List[Dict]) -> Dict[str, Any]:
    """
    分析收费模式，用于辅助重复收费检测
    """
    patterns = {
        'daily_charges': defaultdict(list),
        'frequent_items': defaultdict(int),
        'time_patterns': defaultdict(list)
    }
    
    for item in fee_data:
        charge_code = item.get('收费项目代码')
        charge_date = item.get('收费日期')
        
        if charge_code and charge_date:
            try:
                date_part = charge_date.split(' ')[0]
                time_part = charge_date.split(' ')[1] if ' ' in charge_date else '00:00:00'
                
                patterns['daily_charges'][date_part].append(charge_code)
                patterns['frequent_items'][charge_code] += 1
                patterns['time_patterns'][charge_code].append(time_part)
                
            except Exception as e:
                logger.warning(f"[DuplicateBilling] 分析收费模式时出错: {e}")
                continue
    
    return patterns


def validate_billing_logic(patient_json: dict) -> Dict[str, Any]:
    """
    验证收费逻辑的合理性
    """
    fee_data = patient_json.get("收费报告", [])
    validation_results = {
        'total_items': len(fee_data),
        'unique_codes': len(set(item.get('收费项目代码') for item in fee_data if item.get('收费项目代码'))),
        'date_range': None,
        'suspicious_patterns': []
    }
    
    if fee_data:
        dates = []
        for item in fee_data:
            charge_date = item.get('收费日期')
            if charge_date:
                try:
                    date_part = charge_date.split(' ')[0]
                    dates.append(date_part)
                except:
                    continue
        
        if dates:
            validation_results['date_range'] = {
                'start': min(dates),
                'end': max(dates),
                'span_days': len(set(dates))
            }
    
    return validation_results