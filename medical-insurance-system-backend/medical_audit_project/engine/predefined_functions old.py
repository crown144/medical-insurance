import re
import json
from datetime import datetime
from typing import Dict, List, Any, Union, Optional

def _get_nested_value(data: Dict, path: str) -> Union[List, Any]:
    """获取嵌套字段的值，支持列表处理"""
    if not data or not path:
        return None
        
    keys = path.split('.')
    current = data
    
    # 处理路径中的每一部分
    for key in keys:
        if current is None:
            return None
            
        # 处理列表情况
        if isinstance(current, list):
            results = []
            for item in current:
                # 如果是字典，继续处理
                if isinstance(item, dict) and key in item:
                    value = item[key]
                    if value is not None:
                        # 如果值是非空列表，则展开
                        if isinstance(value, list):
                            results.extend(value)
                        else:
                            results.append(value)
                # 处理其他情况
                elif hasattr(item, key):
                    value = getattr(item, key)
                    if value is not None:
                        results.append(value)
            current = results if results else None
        # 处理字典情况
        elif isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
            
    return current

def extract_data(data: Dict, path: str) -> Union[List, Any]:
    """
    通用数据抽取函数
    支持点分隔路径和数组访问
    """
    # 处理带索引的路径
    if '[' in path and ']' in path:
        path, index = _parse_indexed_path(path)
        target = _get_nested_value(data, path)
        if isinstance(target, list) and len(target) > index:
            return target[index]
        return None
    
    # 处理普通路径
    return _get_nested_value(data, path)

def field_match(data: Dict, path: str, reference_values: List[Any], log_collector: Optional[list] = None) -> bool:
    """检查字段值是否匹配参考值（返回True表示匹配，即条件满足）"""
    if callable(reference_values):
        reference_values = reference_values()
    # 获取字段值
    values = extract_data(data, path)
    
    # 确保值是一个列表
    if not isinstance(values, list):
        values = [values] if values is not None else []
    
    # 过滤掉空值并标准化
    filtered_values = [str(v).strip().lower() for v in values if v is not None and str(v).strip() != ""]
    reference_values = [str(ref).strip().lower() for ref in reference_values]
    
    # 检查是否有匹配项
    if not filtered_values:
        print(f"字段匹配检查: path={path}, 没有有效的值")
        msg = f"字段匹配检查: path={path}, 没有有效的值"
        if log_collector is not None:
            log_collector.append(msg)
        return False  # 没有有效值，不匹配
    
    # 检查是否有匹配的值（支持模糊匹配）
    for value in filtered_values:
        # 完全匹配
        if value in reference_values:
            print(f"字段匹配检查: path={path}, 值 '{value}' 完全匹配参考值 {reference_values}")
            return True
        
        # 部分匹配（参考值包含在值中）
        if any(ref in value for ref in reference_values):
            print(f"字段匹配检查: path={path}, 值 '{value}' 部分包含参考值 {reference_values}")
            return True
        
        # 部分匹配（值包含在参考值中）
        if any(value in ref for ref in reference_values):
            print(f"字段匹配检查: path={path}, 值 '{value}' 被参考值包含 {reference_values}")
            return True
    
    print(f"字段匹配检查: path={path}, 值 {filtered_values} 不匹配参考值 {reference_values}")
    msg = f"字段匹配检查: path={path}, 值 {filtered_values} 不匹配参考值 {reference_values}"
    if log_collector is not None:
        log_collector.append(msg)
    return False

def symptom_match(data: Dict, path: str, reference_values: List[Any], log_collector: Optional[list] = None) -> bool:
    """
    使用大模型检查症状是否匹配
    参数：
    - data: 要检查的数据字典
    - path: 数据路径
    - reference_values: 参考症状列表
    - log_collector: 可选的日志收集器
    返回：
    - bool: True表示匹配，False表示不匹配
    """
    if callable(reference_values):
        reference_values = reference_values()
        
    # 获取字段值
    values = extract_data(data, path)
    
    # 确保值是一个列表
    if not isinstance(values, list):
        values = [values] if values is not None else []
    
    # 过滤掉空值
    filtered_values = [str(v).strip() for v in values if v is not None and str(v).strip() != ""]
    reference_values = [str(ref).strip() for ref in reference_values]
    
    # 检查是否有匹配项
    if not filtered_values:
        print(f"症状匹配检查: path={path}, 没有有效的值")
        msg = f"症状匹配检查: path={path}, 没有有效的值"
        if log_collector is not None:
            log_collector.append(msg)
        return False
    
    try:
        # TODO: 这里需要调用大模型API进行症状匹配
        # 示例：检查每个症状值是否与参考值在语义上匹配
        for value in filtered_values:
            for ref_value in reference_values:
                # 这里应该替换为实际的大模型API调用
                # is_match = llm_api.check_symptom_match(value, ref_value)
                # 临时返回False，等待实际API实现
                is_match = False
                
                if is_match:
                    print(f"症状匹配检查: path={path}, 值 '{value}' 语义匹配参考值 '{ref_value}'")
                    return True
        
        print(f"症状匹配检查: path={path}, 值 {filtered_values} 与参考值 {reference_values} 无语义匹配")
        msg = f"症状匹配检查: path={path}, 值 {filtered_values} 与参考值 {reference_values} 无语义匹配"
        if log_collector is not None:
            log_collector.append(msg)
        return False
        
    except Exception as e:
        print(f"症状匹配检查发生错误: {str(e)}")
        msg = f"症状匹配检查发生错误: {str(e)}"
        if log_collector is not None:
            log_collector.append(msg)
        return False

def _parse_indexed_path(path: str) -> tuple[str, int]:
    """解析带索引的路径"""
    match = re.search(r'^(.+?)$$(\d+)$$(.*)$', path)
    if match:
        base_path = match.group(1)
        index = int(match.group(2))
        suffix = match.group(3)
        if suffix:
            base_path = base_path + suffix
        return base_path, index
    return path, 0



def field_exists(data: Dict, path: str) -> bool:
    """检查字段是否存在"""
    value = extract_data(data, path)
    return value is not None and value != []


def field_contains(data: Dict, path: str, substring: str) -> bool:
    """检查字段值是否包含子串"""
    value = extract_data(data, path)
    
    if value is None:
        return False
        
    if isinstance(value, list):
        return any(substring in str(v) for v in value)
    else:
        return substring in str(value)

def time_after(data: Dict, path: str, reference_date: str) -> bool:
    """检查时间是否在参考时间之后"""
    value = extract_data(data, path)
    if not value:
        return False
    return compare_dates(value, reference_date) > 0

def time_before(data: Dict, path: str, reference_date: str) -> bool:
    """检查时间是否在参考时间之前"""
    value = extract_data(data, path)
    if not value:
        return False
    return compare_dates(value, reference_date) < 0

def time_in_range(data: Dict, path: str, start_date: str, end_date: str) -> bool:
    """检查时间是否在指定范围内"""
    value = extract_data(data, path)
    if not value:
        return False
    return (compare_dates(value, start_date) >= 0 and 
            compare_dates(value, end_date) <= 0)

def compare_dates(date_str1: str, date_str2: str) -> int:
    """比较两个日期字符串"""
    try:
        # 假设日期字符串格式为"YYYY-MM-DD"
        dt1 = datetime.strptime(date_str1, "%Y-%m-%d")
        dt2 = datetime.strptime(date_str2, "%Y-%m-%d")
        
        if dt1 > dt2:
            return 1
        elif dt1 < dt2:
            return -1
        return 0
    except (ValueError, TypeError):
        return 0

def value_comparison(data: Dict, path: str, operator: str, reference_value: Any) -> bool:
    """比较字段值与参考值"""
    value = extract_data(data, path)
    if value is None:
        return False
    
    try:
        if operator == "==":
            return value == reference_value
        elif operator == "!=":
            return value != reference_value
        elif operator == ">":
            return float(value) > float(reference_value)
        elif operator == ">=":
            return float(value) >= float(reference_value)
        elif operator == "<":
            return float(value) < float(reference_value)
        elif operator == "<=":
            return float(value) <= float(reference_value)
    except (ValueError, TypeError):
        pass
    
    return False

def regex_match(data: Dict, path: str, pattern: str) -> bool:
    """检查字段值是否匹配正则表达式"""
    value = extract_data(data, path)
    if value is None:
        return False
        
    pattern = re.compile(pattern)
    
    if isinstance(value, list):
        return any(pattern.match(str(v)) for v in value)
    else:
        return pattern.match(str(value)) is not None

def has_item_match(data: Dict, collection_path: str, field: str, value_match: Any) -> bool:
    """检查集合中是否有元素匹配条件"""
    collection = extract_data(data, collection_path)
    if not collection or not isinstance(collection, list):
        return False
        
    for item in collection:
        if isinstance(item, dict) and field in item:
            if item[field] == value_match:
                return True
    return False

def all_items_match(data: Dict, collection_path: str, field: str, value_match: Any) -> bool:
    """检查集合中所有元素是否匹配条件"""
    collection = extract_data(data, collection_path)
    if not collection or not isinstance(collection, list):
        return False
        
    for item in collection:
        if not (isinstance(item, dict) and field in item):
            return False
        if item[field] != value_match:
            return False
    return True

def get_first_value(data: Dict, path: str) -> Any:
    """获取字段路径的第一个非空值"""
    value = extract_data(data, path)
    if isinstance(value, list) and value:
        return value[0]
    return value

def get_last_value(data: Dict, path: str) -> Any:
    """获取字段路径的最后一个非空值"""
    value = extract_data(data, path)
    if isinstance(value, list) and value:
        return value[-1]
    return value

def count_values(data: Dict, path: str) -> int:
    """计算字段路径的值数量"""
    value = extract_data(data, path)
    if isinstance(value, list):
        return len(value)
    return 1 if value is not None else 0

# 预定义函数映射表
PREDEFINED_FUNCTIONS_MAP = {
    'extract': extract_data,
    'fieldExists': field_exists,
    'fieldMatch': field_match,
    'symptomMatch': symptom_match,
    'fieldContains': field_contains,
    'timeAfter': time_after,
    'timeBefore': time_before,
    'timeInRange': time_in_range,
    'valueComparison': value_comparison,
    'regexMatch': regex_match,
    'hasItemMatch': has_item_match,
    'allItemsMatch': all_items_match,
    'firstValue': get_first_value,
    'lastValue': get_last_value,
    'count': count_values
}