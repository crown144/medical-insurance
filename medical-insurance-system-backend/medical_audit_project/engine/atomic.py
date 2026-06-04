# atomic.py
from .utils import get_value

def match_field(record: dict, path: str, target_values: list) -> bool:
    """
    原子函数：检查 record 中 path 对应的值是否包含在 target_values 中
    """
    actual_val = get_value(record, path)
    
    if actual_val is None:
        return False
        
    # 如果取出的是列表（如所有诊断），求交集
    if isinstance(actual_val, list):
        # 扁平化并过滤 None
        flat_val = set([str(v) for v in actual_val if v is not None])
        targets = set(target_values)
        return not flat_val.isdisjoint(targets)
    
    # 如果是单值
    return str(actual_val) in target_values

def compare_value(record: dict, path: str, operator: str, threshold: float) -> bool:
    """
    原子函数：数值比较
    """
    val = get_value(record, path)
    if val is None:
        return False
    
    try:
        val = float(val)
        threshold = float(threshold)
    except:
        return False
        
    if operator == '>': return val > threshold
    if operator == '>=': return val >= threshold
    if operator == '<': return val < threshold
    if operator == '<=': return val <= threshold
    if operator == '==': return val == threshold
    if operator == '!=': return val != threshold
    return False

def llm_predicate(record: dict, context_fields: list, condition: str) -> bool:
    """
    原子函数：LLM 语义判断 (Mock版本，实际需调用API)
    """
    # 这里只是模拟，实际需要你接入 OpenAI/DeepSeek 接口
    print(f"[LLM Check] Fields: {context_fields}, Question: {condition}")
    return True # 默认放行，方便测试