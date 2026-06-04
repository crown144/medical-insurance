"""
增强重复收费检测核心模块
Enhanced Duplicate Charging Detection Core
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

from .utils import ChargeDataProcessor
from .package_detector import PackageChargeDetector
from .ai_analyzer import AIViolationAnalyzer
from .father_child_detector import FatherChildDuplicateDetector

logger = logging.getLogger(__name__)


class EnhancedDuplicateDetector:
    """增强的重复收费检测器"""
    
    def __init__(self, enable_ai: bool = False, deepseek_config: Optional[Dict] = None):
        """
        初始化检测器
        
        Args:
            enable_ai: 是否启用AI分析
            deepseek_config: DeepSeek API配置
        """
        self.enable_ai = enable_ai
        self.data_processor = ChargeDataProcessor()
        self.package_detector = PackageChargeDetector()
        self.father_child_detector = FatherChildDuplicateDetector()
        self.ai_analyzer = AIViolationAnalyzer(deepseek_config) if enable_ai else None
        
    def detect_all_violations(self, patient_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        检测所有类型的重复收费违规
        
        Args:
            patient_json: 病历JSON数据
            
        Returns:
            违规结果列表
        """
        violations = []
        
        # 1. 基础重复收费检测
        basic_violations = self._detect_basic_duplicates(patient_json)
        violations.extend(basic_violations)
        
        # 2. 组套重复收费检测
        package_violations = self.package_detector.detect_package_duplicates(patient_json)
        violations.extend(package_violations)

        # 3. 父子项目重复收费检测（1016_type1逻辑移植）
        father_child_violations = self.father_child_detector.detect(patient_json)
        violations.extend(father_child_violations)

        # 4. AI分析和假性违规过滤
        if self.ai_analyzer and violations:
            violations = self.ai_analyzer.filter_false_positives(violations, patient_json)
            
        logger.info(f"[EnhancedDuplicate] 总计检测到 {len(violations)} 项重复收费违规")
        return violations
    
    def _detect_basic_duplicates(self, patient_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        基础重复收费检测（925标准）
        
        Args:
            patient_json: 病历JSON数据
            
        Returns:
            基础重复收费违规列表
        """
        fee_data = patient_json.get("收费报告", [])
        if not fee_data:
            logger.warning("[EnhancedDuplicate] 病历JSON中未找到收费报告数据")
            return []
            
        violations = []
        
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

            # 检测组套重复收费（925标准）
            for charge_code, same_code_charges in code_groups.items():
                if len(same_code_charges) > 1:
                    # 检查是否有多个不同的ORDER_ITEM_CODE
                    order_item_codes = set()
                    for charge in same_code_charges:
                        order_code = charge.get("ORDER_ITEM_CODE", "")
                        if order_code and order_code != "xxx":
                            order_item_codes.add(order_code)
                    
                    # 只有当存在多个不同的ORDER_ITEM_CODE时才认为是违规（925标准）
                    if len(order_item_codes) > 1:
                        violation = self._create_925_standard_violation(
                            charge_code, same_code_charges, charge_time, order_item_codes, patient_json
                        )
                        if violation:
                            violations.append(violation)
        
        logger.info(f"[EnhancedDuplicate] 925标准检测发现 {len(violations)} 项违规")
        return violations
    
    def _create_925_standard_violation(
        self, 
        charge_code: str, 
        charges: List[Dict], 
        charge_time: str,
        order_item_codes: set,
        patient_json: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        创建符合925标准的重复收费违规记录
        
        Args:
            charge_code: 收费项目代码
            charges: 重复的收费记录列表
            charge_time: 收费时间
            order_item_codes: 不同的ORDER_ITEM_CODE集合
            patient_json: 病历数据
            
        Returns:
            违规记录或None
        """
        if not charges:
            return None
            
        first_charge = charges[0]
        charge_name = first_charge.get('收费项目名称', '未知项目')
        
        logger.info(f"[EnhancedDuplicate] 发现组套重复收费: {charge_name} (代码: {charge_code}) 在 {charge_time} 有 {len(order_item_codes)} 个不同组套")
        
        # 计算总金额和详细信息
        total_amount = 0
        duplicate_items = []
        highlights = []
        
        for i, charge in enumerate(charges):
            try:
                unit_price = float(charge.get('项目单价', 0))
                quantity = float(charge.get('数量', 1))
                amount = unit_price * quantity
                total_amount += amount
                
                duplicate_items.append({
                    '收费项目代码': charge.get('收费项目代码'),
                    '收费项目名称': charge.get('收费项目名称'),
                    '收费日期': charge.get('收费日期'),
                    '项目单价': charge.get('项目单价'),
                    '数量': charge.get('数量'),
                    '金额': amount,
                    'ORDER_ITEM_CODE': charge.get('ORDER_ITEM_CODE', '')
                })
                
                # 生成高亮信息
                original_index = charge.get('_index', i)
                highlights.append({
                    'field_path': f'收费报告[{original_index}]',
                    'highlighted_text': f'{charge_name} - {charge.get("收费日期")} - 单价:{charge.get("项目单价")} - 数量:{charge.get("数量")}'
                })
                
            except (ValueError, TypeError) as e:
                logger.warning(f"[EnhancedDuplicate] 计算金额失败: {e}")
                continue
        
        # 获取患者信息
        patient_id = self.data_processor.extract_patient_id(patient_json)
        
        return {
            'violation': True,
            'rule': {
                'rule_id': f'ENHANCED_925_STANDARD_{charge_code}',
                'type': '重复收费-组套',
                'drug_name': charge_name,
                'description': f'检测到同一收费项目在不同组套中重复收费'
            },
            'reason': f'收费项目"{charge_name}"(代码:{charge_code})在{charge_time}存在组套重复收费，涉及{len(order_item_codes)}个不同组套，总金额:{total_amount:.2f}元',
            'item': {
                '患者住院号': patient_id,
                '收费项目代码': charge_code,
                '收费项目名称': charge_name,
                '重复日期': charge_time,
                '组套数量': len(order_item_codes),
                '重复次数': len(charges),
                '总金额': total_amount,
                '明细': duplicate_items
            },
            'highlights': highlights,
            'violation_type': 'package_duplicate',
            'severity': 'high' if len(order_item_codes) > 2 else 'medium'
        }
    
    def get_detection_summary(self, violations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        获取检测结果摘要
        
        Args:
            violations: 违规结果列表
            
        Returns:
            检测摘要
        """
        summary = {
            'total_violations': len(violations),
            'basic_duplicates': 0,
            'package_duplicates': 0,
            'ai_filtered': 0,
            'total_amount': 0,
            'severity_distribution': {'low': 0, 'medium': 0, 'high': 0}
        }
        
        for violation in violations:
            violation_type = violation.get('violation_type', 'unknown')
            if violation_type == 'basic_duplicate':
                summary['basic_duplicates'] += 1
            elif violation_type == 'package_duplicate':
                summary['package_duplicates'] += 1
                
            # 统计金额
            item = violation.get('item', {})
            amount = item.get('总金额', 0)
            if isinstance(amount, (int, float)):
                summary['total_amount'] += amount
                
            # 统计严重程度
            severity = violation.get('severity', 'medium')
            if severity in summary['severity_distribution']:
                summary['severity_distribution'][severity] += 1
        
        return summary