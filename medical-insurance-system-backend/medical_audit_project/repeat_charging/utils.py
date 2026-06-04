"""
重复收费检测工具模块
Utility functions for duplicate charging detection
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import defaultdict
import re

logger = logging.getLogger(__name__)


class ChargeDataProcessor:
    """收费数据处理器"""
    
    def __init__(self):
        self.time_tolerance = timedelta(hours=2)  # 时间容差
        
    def group_by_time_batch(self, fee_data: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """
        按时间批次分组收费数据
        
        Args:
            fee_data: 收费数据列表
            
        Returns:
            按时间批次分组的数据
        """
        time_groups = defaultdict(list)
        
        for charge in fee_data:
            # 尝试多种可能的日期时间字段
            charge_datetime = charge.get('收费日期', '') or charge.get('收费时间', '') or charge.get('CHARGE_DATE', '')
            
            # 解析日期和时间
            charge_date, charge_time = self._parse_datetime(charge_datetime)
            
            # 生成时间批次标识
            time_batch = self._generate_time_batch(charge_date, charge_time)
            time_groups[time_batch].append(charge)
            
        return dict(time_groups)
    
    def _parse_datetime(self, datetime_str: str) -> tuple:
        """
        解析日期时间字符串
        
        Args:
            datetime_str: 日期时间字符串
            
        Returns:
            (日期, 时间) 元组
        """
        if not datetime_str:
            return '', ''
            
        try:
            # 尝试解析完整的日期时间格式
            if ' ' in datetime_str:
                date_part, time_part = datetime_str.split(' ', 1)
                return date_part, time_part
            else:
                # 只有日期
                return datetime_str, ''
        except Exception:
            return datetime_str, ''
    
    def _generate_time_batch(self, charge_date: str, charge_time: str = '') -> str:
        """
        生成时间批次标识
        
        Args:
            charge_date: 收费日期
            charge_time: 收费时间
            
        Returns:
            时间批次字符串
        """
        if not charge_date:
            return 'unknown_date'
            
        # 如果有具体时间，按小时分组
        if charge_time:
            try:
                # 解析时间并按2小时窗口分组
                time_parts = charge_time.split(':')
                if len(time_parts) >= 2:
                    hour = int(time_parts[0])
                    # 按2小时窗口分组
                    batch_hour = (hour // 2) * 2
                    return f"{charge_date}_{batch_hour:02d}:00-{batch_hour+1:02d}:59"
            except (ValueError, IndexError):
                pass
                
        # 默认按日期分组
        return charge_date
    
    def extract_patient_id(self, patient_json: Dict[str, Any]) -> str:
        """
        提取患者住院号
        
        Args:
            patient_json: 病历JSON数据
            
        Returns:
            患者住院号
        """
        # 尝试多种可能的字段名
        possible_fields = [
            '患者住院号', 'patient_id', 'admission_id', 
            '住院号', 'inpatient_id', 'id'
        ]
        
        for field in possible_fields:
            if field in patient_json:
                return str(patient_json[field])
                
        # 从收费报告中提取
        fee_data = patient_json.get("收费报告", [])
        if fee_data and isinstance(fee_data, list) and len(fee_data) > 0:
            first_charge = fee_data[0]
            for field in possible_fields:
                if field in first_charge:
                    return str(first_charge[field])
                    
        return 'unknown_patient'
    
    def normalize_charge_code(self, charge_code: str) -> str:
        """
        标准化收费项目代码
        
        Args:
            charge_code: 原始收费代码
            
        Returns:
            标准化后的代码
        """
        if not charge_code:
            return ''
            
        # 移除空格和特殊字符
        normalized = re.sub(r'[^\w\-\.]', '', str(charge_code).strip())
        return normalized.upper()
    
    def calculate_charge_amount(self, charge: Dict[str, Any]) -> float:
        """
        计算收费金额
        
        Args:
            charge: 收费记录
            
        Returns:
            计算后的金额
        """
        try:
            unit_price = float(charge.get('项目单价', 0))
            quantity = float(charge.get('数量', 1))
            return unit_price * quantity
        except (ValueError, TypeError):
            logger.warning(f"[ChargeProcessor] 无法计算金额: {charge}")
            return 0.0
    
    def is_valid_charge(self, charge: Dict[str, Any]) -> bool:
        """
        验证收费记录是否有效
        
        Args:
            charge: 收费记录
            
        Returns:
            是否有效
        """
        # 检查必要字段
        required_fields = ['收费项目代码', '收费项目名称']
        for field in required_fields:
            if not charge.get(field):
                return False
                
        # 检查代码是否为占位符
        charge_code = charge.get('收费项目代码', '')
        if charge_code in ['xxx', 'XXX', '', 'null', 'NULL']:
            return False
            
        return True
    
    def group_charges_by_code(self, charges: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """
        按收费代码分组
        
        Args:
            charges: 收费记录列表
            
        Returns:
            按代码分组的收费记录
        """
        code_groups = defaultdict(list)
        
        for charge in charges:
            if not self.is_valid_charge(charge):
                continue
                
            charge_code = self.normalize_charge_code(charge.get('收费项目代码', ''))
            if charge_code:
                code_groups[charge_code].append(charge)
                
        return dict(code_groups)
    
    def extract_order_codes(self, charge: Dict[str, Any]) -> List[str]:
        """
        提取医嘱代码列表
        
        Args:
            charge: 收费记录
            
        Returns:
            医嘱代码列表
        """
        order_codes = []
        
        # 检查ORDER_ITEM_CODE字段
        order_item_code = charge.get('ORDER_ITEM_CODE', '')
        if order_item_code and order_item_code != 'xxx':
            # 可能包含多个代码，用分隔符分割
            codes = re.split(r'[,;|]', str(order_item_code))
            order_codes.extend([code.strip() for code in codes if code.strip()])
            
        return order_codes
    
    def format_violation_amount(self, amount: float) -> str:
        """
        格式化违规金额
        
        Args:
            amount: 金额
            
        Returns:
            格式化后的金额字符串
        """
        if amount == 0:
            return "0.00元"
        elif amount < 1000:
            return f"{amount:.2f}元"
        elif amount < 10000:
            return f"{amount/1000:.1f}千元"
        else:
            return f"{amount/10000:.1f}万元"