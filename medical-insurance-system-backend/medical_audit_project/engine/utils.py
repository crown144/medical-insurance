# utils.py
from typing import Any, List, Union

def get_value(data: dict, path: str) -> Any:
    """
    辅助函数：根据路径 'a.b.c' 从字典中取值。
    支持处理列表：如果路径中间遇到列表，会提取列表中所有项的对应字段。
    """
    if not data or not path:
        return None
        
    keys = path.split('.')
    current = data
    
    for i, key in enumerate(keys):
        if isinstance(current, dict):
            current = current.get(key)
        elif isinstance(current, list):
            # 如果遇到列表，发散提取剩余路径的值
            remaining_path = '.'.join(keys[i:])
            return [get_value(item, remaining_path) for item in current]
        else:
            return None
            
        if current is None:
            return None
            
    return current