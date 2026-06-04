# business.py
from datetime import datetime
from .utils import get_value

def check_limit(record: dict, current_item: dict, limit_type: str, threshold: str) -> bool:
    """
    业务函数：检查各种限制 (时间、价格、数量)
    字段名符合海南模板.json中的定义
    """
    # 场景1：检查当前收费项单价 (不需要查病历，只查 current_item)
    if limit_type == 'price':
        # 根据海南模板.json，收费报告中的字段是"项目单价"
        price = current_item.get('项目单价', 0)
        try:
            price = float(price) if price else 0
        except (ValueError, TypeError):
            price = 0
        return price <= float(threshold)
        
    # 场景2：检查支付时长 (需要查病历入院时间和当前收费时间)
    elif limit_type == 'pay_duration':
        # 根据海南模板.json，入院日期在"基本信息.入院日期"或"出院记录.入院日期"
        admission_date_str = get_value(record, '基本信息.入院日期')
        if not admission_date_str:
            # 如果基本信息中没有，尝试从出院记录中获取
            admission_date_str = get_value(record, '出院记录.入院日期')
        
        # 根据海南模板.json，收费报告中的字段是"收费日期"
        charge_date_str = current_item.get('收费日期')
        
        if not admission_date_str or not charge_date_str:
            return True # 数据缺失默认通过
            
        try:
            d1 = datetime.strptime(admission_date_str, "%Y-%m-%d")
            d2 = datetime.strptime(charge_date_str, "%Y-%m-%d")
            days = (d2 - d1).days
            return days <= int(threshold.replace('d', ''))
        except:
            return False

    return True