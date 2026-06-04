"""
组套重复收费检测模块
Package Duplicate Charging Detection Module
"""

import logging
from typing import List, Dict, Any, Optional, Set
from collections import defaultdict
import pandas as pd

from .utils import ChargeDataProcessor

logger = logging.getLogger(__name__)


class PackageChargeDetector:
    """组套重复收费检测器"""
    
    def __init__(self):
        self.data_processor = ChargeDataProcessor()
        
    def detect_package_duplicates(self, patient_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        检测组套重复收费违规
        
        Args:
            patient_json: 病历JSON数据
            
        Returns:
            组套重复收费违规列表
        """
        fee_data = patient_json.get("收费报告", [])
        if not fee_data:
            logger.warning("[PackageDetector] 病历JSON中未找到收费报告数据")
            return []
            
        violations = []
        
        # 转换为DataFrame便于分析
        df = self._prepare_dataframe(fee_data, patient_json)
        if df.empty:
            logger.warning("[PackageDetector] 无有效收费数据")
            return []
            
        # 按收费项目代码和时间分组
        package_groups = self._group_by_charge_item_and_time(df)
        
        # 检测每个分组中的组套重复
        for group_key, group_info in package_groups.items():
            violation = self._analyze_package_group(group_info, df, patient_json)
            if violation:
                violations.append(violation)
                
        logger.info(f"[PackageDetector] 组套检测发现 {len(violations)} 项违规")
        return violations
    
    def _prepare_dataframe(self, fee_data: List[Dict], patient_json: Dict[str, Any]) -> pd.DataFrame:
        """
        准备分析用的DataFrame
        
        Args:
            fee_data: 收费数据
            patient_json: 病历数据
            
        Returns:
            处理后的DataFrame
        """
        records = []
        patient_id = self.data_processor.extract_patient_id(patient_json)
        
        for i, charge in enumerate(fee_data):
            if not self.data_processor.is_valid_charge(charge):
                continue
                
            # 提取医嘱代码
            order_codes = self.data_processor.extract_order_codes(charge)
            
            # 如果有多个医嘱代码，说明可能涉及组套
            if len(order_codes) > 1:
                record = {
                    'index': i,
                    '住院号': patient_id,
                    '收费项目代码': charge.get('收费项目代码', ''),
                    '收费项目名称': charge.get('收费项目名称', ''),
                    '收费时间': charge.get('收费日期', '') + ' ' + charge.get('收费时间', ''),
                    '收费日期': charge.get('收费日期', ''),
                    '项目单价': charge.get('项目单价', 0),
                    '数量': charge.get('数量', 1),
                    'ORDER_ITEM_CODE': charge.get('ORDER_ITEM_CODE', ''),
                    'order_codes': order_codes,
                    'package_count': len(order_codes)
                }
                
                # 尝试获取组套名称
                record['组套项目名称'] = self._extract_package_names(charge, order_codes)
                records.append(record)
        
        return pd.DataFrame(records)
    
    def _extract_package_names(self, charge: Dict[str, Any], order_codes: List[str]) -> List[str]:
        """
        提取组套项目名称
        
        Args:
            charge: 收费记录
            order_codes: 医嘱代码列表
            
        Returns:
            组套名称列表
        """
        package_names = []
        
        # 从收费项目名称推断组套名称
        charge_name = charge.get('收费项目名称', '')
        
        # 如果名称包含"组套"关键词
        if '组套' in charge_name:
            package_names.append(charge_name)
        else:
            # 根据医嘱代码生成组套名称
            for code in order_codes:
                package_name = f"组套项目_{code}"
                package_names.append(package_name)
                
        return package_names
    
    def _group_by_charge_item_and_time(self, df: pd.DataFrame) -> Dict[str, Dict]:
        """
        按收费项目代码和收费时间分组
        
        Args:
            df: 收费数据DataFrame
            
        Returns:
            分组数据
        """
        if df.empty:
            return {}
            
        # 创建分组键
        df['group_key'] = (df['住院号'] + '_' + 
                          df['收费项目代码'] + '_' + 
                          df['收费日期'])  # 按日期分组，不用精确时间
        
        grouped = df.groupby('group_key')
        groups_data = {}
        
        for group_key, group_df in grouped:
            # 收集所有组套名称
            all_package_names = []
            for _, row in group_df.iterrows():
                package_names = row.get('组套项目名称', [])
                if isinstance(package_names, list):
                    all_package_names.extend(package_names)
                elif isinstance(package_names, str):
                    all_package_names.append(package_names)
            
            # 去重并过滤
            unique_packages = list(set([name for name in all_package_names if name]))
            
            # 如果有多个不同的组套，可能存在重复收费
            if len(unique_packages) > 1:
                groups_data[group_key] = {
                    'package_names': unique_packages,
                    'rows': group_df.index.tolist(),
                    'charge_item_code': group_df['收费项目代码'].iloc[0],
                    'charge_item_name': group_df['收费项目名称'].iloc[0],
                    'charge_time': group_df['收费时间'].iloc[0],
                    'charge_date': group_df['收费日期'].iloc[0],
                    'total_amount': self._calculate_group_amount(group_df),
                    'duplicate_count': len(group_df)
                }
        
        logger.info(f"[PackageDetector] 找到 {len(groups_data)} 个需要判断的组套组")
        return groups_data
    
    def _calculate_group_amount(self, group_df: pd.DataFrame) -> float:
        """
        计算分组总金额
        
        Args:
            group_df: 分组数据
            
        Returns:
            总金额
        """
        total = 0.0
        for _, row in group_df.iterrows():
            try:
                unit_price = float(row.get('项目单价', 0))
                quantity = float(row.get('数量', 1))
                total += unit_price * quantity
            except (ValueError, TypeError):
                continue
        return total
    
    def _analyze_package_group(
        self, 
        group_info: Dict, 
        df: pd.DataFrame, 
        patient_json: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        分析组套分组是否存在重复收费
        
        Args:
            group_info: 分组信息
            df: 完整数据框
            patient_json: 病历数据
            
        Returns:
            违规记录或None
        """
        charge_code = group_info['charge_item_code']
        charge_name = group_info['charge_item_name']
        package_names = group_info['package_names']
        
        # 基本判断：同一收费项目在多个组套中出现
        if len(package_names) < 2:
            return None
            
        # 构建违规记录
        patient_id = self.data_processor.extract_patient_id(patient_json)
        
        # 生成详细信息
        duplicate_details = []
        highlights = []
        
        for i, row_idx in enumerate(group_info['rows']):
            row = df.loc[row_idx]
            detail = {
                '收费项目代码': charge_code,
                '收费项目名称': charge_name,
                '收费日期': row.get('收费日期', ''),
                '项目单价': row.get('项目单价', 0),
                '数量': row.get('数量', 1),
                '涉及组套': row.get('组套项目名称', []),
                'ORDER_ITEM_CODE': row.get('ORDER_ITEM_CODE', '')
            }
            duplicate_details.append(detail)
            
            # 生成高亮
            highlights.append({
                'field_path': f'收费报告[{row.get("index", i)}]',
                'highlighted_text': f'{charge_name} - 组套重复 - {row.get("收费日期")}'
            })
        
        return {
            'violation': True,
            'rule': {
                'rule_id': 'ENHANCED_PACKAGE_001',
                'type': '组套重复收费',
                'drug_name': charge_name,
                'description': '检测到同一收费项目在多个组套中重复收费'
            },
            'reason': f'收费项目"{charge_name}"(代码:{charge_code})在{len(package_names)}个组套中重复收费：{", ".join(package_names)}',
            'item': {
                '患者住院号': patient_id,
                '收费项目代码': charge_code,
                '收费项目名称': charge_name,
                '重复日期': group_info['charge_date'],
                '涉及组套': package_names,
                '重复次数': group_info['duplicate_count'],
                '总金额': group_info['total_amount'],
                '明细': duplicate_details
            },
            'highlights': highlights,
            'violation_type': 'package_duplicate',
            'severity': 'high' if len(package_names) > 2 else 'medium',
            'package_analysis': {
                'requires_ai_verification': True,
                'package_names': package_names,
                'charge_item': charge_name
            }
        }