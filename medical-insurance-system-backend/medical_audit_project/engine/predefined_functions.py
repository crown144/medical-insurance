import re
import json
from datetime import datetime
from typing import Dict, List, Any, Union, Optional
from .llm_api import LLMApiClient 
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- 核心改造：新的数据提取函数，能返回路径和值 ---
def extract_data_with_paths(data: Any, path: str, current_path: str = '$') -> List[Dict]:
    """
    递归地从数据中提取值，并返回一个包含 {path, value} 的字典列表。
    """
    keys = path.split('.', 1)
    current_key = keys[0]
    remaining_path = keys[1] if len(keys) > 1 else None

    results = []

    if isinstance(data, list):
        for i, item in enumerate(data):
            item_path = f"{current_path}[{i}]"
            # 继续在列表的每个元素中递归查找
            results.extend(extract_data_with_paths(item, path, item_path))
        return results

    if isinstance(data, dict):
        if current_key in data:
            new_data = data[current_key]
            new_path = f"{current_path}.{current_key}"
            if remaining_path:
                results.extend(extract_data_with_paths(new_data, remaining_path, new_path))
            else:
                # 到达路径末端
                results.append({"path": new_path, "value": new_data})
        return results
    
    return []
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


def field_match(data: Dict, paths: Union[str, List[str]], reference_values: List[Any]) -> dict:
    if callable(reference_values):
        reference_values = reference_values()
    if isinstance(paths, str):
        paths = [paths]
    
    all_extracted_items = [] # 存储 {path, value}
    for path in paths:
        all_extracted_items.extend(extract_data_with_paths(data, path))

    filtered_values = [str(item['value']).strip().lower() for item in all_extracted_items if item.get('value') is not None]
    # logger.info(f"提取路径 {paths} 得到值: {filtered_values}")
    reference_values = [str(ref).strip().lower() for ref in reference_values]
    
    # 检查是否有匹配项
    for value in filtered_values:
        if value in reference_values or any(ref in value for ref in reference_values) or any(value in ref for ref in reference_values):
            # 匹配成功，返回所有提取到的路径作为证据
            evidence = [{"field_path": item['path'], "highlighted_text": str(item['value'])} for item in all_extracted_items]
            return {"pass": True, "evidence": evidence, "reference_values": reference_values}

    # 匹配失败时，返回所有提取到的路径和值作为反向证据
    evidence = [{"field_path": item['path'], "highlighted_text": str(item['value'])} for item in all_extracted_items]
    return {"pass": False, "evidence": evidence, "reference_values": reference_values}
def audit_patient_symptoms(
    data: Dict,
    drug_limit: str,
    llm_api_client=None,
    log_collector: Optional[list] = None
) -> str:
    """
    综合提取患者症状并调用LLM API判断是否满足药品限制条件，并记录日志
    参数:
        data: 患者数据字典
        drug_limit: 药品限制条件字符串
        llm_api_client: 可选，传入LLMApiClient实例，未传则自动导入并实例化
        log_collector: 可选，日志收集list
    返回:
        LLM API返回的审核结果字符串
    """
    logger.info(f"调用 audit_patient_symptoms, drug_limit={drug_limit}")
    # 提取症状
    symptom_paths = [
        "入院记录.主诉",
        "入院记录.现病史",
        "入院记录.体格检查",
        "入院记录.专科情况",
        "入院记录.辅助检查"
    ]
    symptoms = []
    for path in symptom_paths:
        value = extract_data(data, path)
        if value and value != "文本中未提及该内容":
            if isinstance(value, list):
                # 展开列表并过滤空内容
                for v in value:
                    if v and v != "文本中未提及该内容":
                        symptoms.append(str(v))
            else:
                symptoms.append(str(value))
            if log_collector is not None:
                log_collector.append(f"提取症状: 路径={path}, 值={value}")
        else:
            if log_collector is not None:
                log_collector.append(f"提取症状: 路径={path}, 未提及或无内容")

    # 组装prompt
    prompt = f"""你是一名医学审核专家，请判断患者的症状是否满足药品的限制条件。

【药品限制】
{drug_limit}

【患者症状】
{', '.join(symptoms)}

请直接回答“是否满足限制条件”，并简要说明理由。
如果存在症状，可直接判别为满足，无需再参考诊断信息。
输出格式如下：
满足/不满足
理由：xxx
"""
    # if log_collector is not None:
    #     log_collector.append(f"生成Prompt:\n{prompt}")

    # 调用LLM API
    if llm_api_client is None:
        from .llm_api import LLMApiClient
        llm_api_client = LLMApiClient()
    result = llm_api_client.chat(prompt)
    # 只要包含“满足”就通过，否则违规
    is_pass = not("不满足" in result)
    evidence = [
        {"field_path": "症状审核", "highlighted_text": result}
    ]
    reference_values = [drug_limit]
    logger.info(f"audit_patient_symptoms 返回: pass={is_pass}, evidence={evidence}, reference_values={reference_values}")
    return {"pass": is_pass, "evidence": evidence, "reference_values": reference_values}



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

def limit_time(data: Dict, mode: str, drug_name: str, threshold_str: str) -> dict:
    """根据不同模式限制时间跨度，目前仅支持'pay'模式"""

    def _parse_datetime(dt_str: Any) -> Optional[datetime]:
        if not isinstance(dt_str, str):
            return None
        dt_str = dt_str.strip()
        if not dt_str:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(dt_str, fmt)
            except ValueError:
                continue
        return None

    try:
        threshold = float(threshold_str)
    except (TypeError, ValueError):
        return {
            "pass": False,
            "evidence": [{"field_path": "limit_time.threshold", "highlighted_text": str(threshold_str)}],
            "reference_values": [f"限制支付时长不超过{threshold_str}"],
        }

    mode_key = str(mode).strip().lower()
    if mode_key != 'pay':
        return {
            "pass": False,
            "evidence": [{"field_path": "limit_time.mode", "highlighted_text": str(mode)}],
            "reference_values": ["pay"],
        }

    target_name = str(drug_name).strip().lower()
    medications = data.get("用药信息")
    if not isinstance(medications, list) or not medications:
        return {
            "pass": False,
            "evidence": [{"field_path": "用药信息", "highlighted_text": "未找到匹配数据"}],
            "reference_values": [f"限制支付时长不超过{threshold_str}"],
        }

    time_records: List[Dict[str, Any]] = []
    for idx, item in enumerate(medications):
        if not isinstance(item, dict):
            continue
        current_name = str(item.get("药品通用名", "")).strip().lower()
        if current_name != target_name:
            continue
        for key, value in item.items():
            if not (isinstance(key, str) and re.match(r"^第\d+次开药$", key)):
                continue
            if not isinstance(value, dict):
                continue
            time_field = "药品收费时间" if "药品收费时间" in value else "收费时间" if "收费时间" in value else None
            if not time_field:
                continue
            time_str = value.get(time_field)
            parsed = _parse_datetime(time_str)
            if not parsed:
                continue
            time_records.append({
                "datetime": parsed,
                "path": f"用药信息[{idx}].{key}.{time_field}",
                "display": str(time_str),
            })

    if not time_records:
        return {
            "pass": False,
            "evidence": [{"field_path": "用药信息", "highlighted_text": "未找到收费时间"}],
            "reference_values": [f"限制支付时长不超过{threshold_str}"],
        }

    earliest = min(time_records, key=lambda x: x["datetime"])
    latest = max(time_records, key=lambda x: x["datetime"])
    span_days = (latest["datetime"].date() - earliest["datetime"].date()).days

    sorted_records = sorted(time_records, key=lambda x: x["datetime"])
    evidence = [
        {"field_path": rec["path"], "highlighted_text": rec["display"]}
        for rec in sorted_records
    ]
    evidence.append({"field_path": "limit_time.span_days", "highlighted_text": f"{span_days}"})

    return {
        "pass": span_days <= threshold,
        "evidence": evidence,
        "reference_values": [f"限制支付时长不超过{threshold_str}"],
    }

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

def value_comparison(data: Dict, path_str: str, operator: str, reference_value: Any) -> dict:
    items = extract_data_with_paths(data, path_str)
    
    if not items:
        return {"pass": False, "evidence": [{"field_path": path_str, "highlighted_text": "未找到值"}]}

    # 只比较第一个找到的值
    item = items[0]
    value = item['value']
    path = item['path']

    try:
        is_pass = False
        numeric_value = float(value)
        numeric_ref_value = float(reference_value)

        if operator == "==": is_pass = numeric_value == numeric_ref_value
        elif operator == "!=": is_pass = numeric_value != numeric_ref_value
        elif operator == ">": is_pass = numeric_value > numeric_ref_value
        elif operator == ">=": is_pass = numeric_value >= numeric_ref_value
        elif operator == "<": is_pass = numeric_value < numeric_ref_value
        elif operator == "<=": is_pass = numeric_value <= numeric_ref_value
        
        evidence = [{"field_path": path, "highlighted_text": str(value)}]
        return {"pass": is_pass, "evidence": evidence}

    except (ValueError, TypeError):
        # 如果无法转为数字，则按字符串比较
        str_value = str(value)
        str_ref_value = str(reference_value)
        is_pass = False
        if operator == "==": is_pass = str_value == str_ref_value
        elif operator == "!=": is_pass = str_value != str_ref_value
        
        evidence = [{"field_path": path, "highlighted_text": str_value}]
        return {"pass": is_pass, "evidence": evidence}

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
def eval_logic_expression(expression, context):
    """
    支持 and/or 混合的表达式求值，递归收集违规证据。
    只要整条表达式通过，什么都不收集。
    如果违规，and遇到第一个失败就收集，or只有全部失败才收集所有。
    """
    def parse(expr):
        expr = expr.strip()
        # 去除最外层括号
        while expr.startswith('(') and expr.endswith(')'):
            # 检查括号是否配对
            count = 0
            for i, c in enumerate(expr):
                if c == '(': count += 1
                elif c == ')': count -= 1
                if count == 0 and i < len(expr) - 1:
                    break
            else:
                expr = expr[1:-1].strip()
                continue
            break
        # 先分割and
        parts = split_expr(expr, 'and')
        if len(parts) > 1:
            return ('and', [parse(p) for p in parts])
        # 再分割or
        parts = split_expr(expr, 'or')
        if len(parts) > 1:
            return ('or', [parse(p) for p in parts])
        return expr

    def split_expr(expr, op):
        res = []
        depth = 0
        last = 0
        i = 0
        while i < len(expr):
            if expr[i] == '(': depth += 1
            elif expr[i] == ')': depth -= 1
            elif depth == 0 and expr[i:i+len(op)+2] == f' {op} ':
                res.append(expr[last:i])
                last = i+len(op)+2
                i += len(op)+1
            i += 1
        res.append(expr[last:])
        return [r.strip() for r in res if r.strip()]

    def eval_node(node):
        if isinstance(node, str):
            try:
                result = eval(node, context)
                # print(f"Evaluating expression '{node}' resulted in: {result}")
                if isinstance(result, dict) and 'reference_values' in result:
                    ref = result['reference_values']
                else:
                    ref = []
                if not isinstance(result, dict) or not result.get('pass'):
                    ev = result.get('evidence', []) if isinstance(result, dict) else []
                    print(f"Expression '{node}' evaluation failed, evidence: {ev}")
                    # logger.info(f"表达式 '{node}' 求值不通过，证据: {ev}")
                    return {'pass': False, 'evidence': ev, 'reference_values': ref}
                # logger.info(f"表达式 '{node}' 求值通过，证据: {result.get('evidence', []) if isinstance(result, dict) else []}")
                return {'pass': True}
            except Exception as e:
                print(f"表达式 '{node}' 求值出错: {e}")
                return {'pass': False, 'evidence': [{"error": str(e)}], 'reference_values': []}
        op, children = node
        if op == 'and':
            for child in children:
                r = eval_node(child)
                if not r.get('pass'):
                    return r
            return {'pass': True}
        elif op == 'or':
            failed_evidence = []
            failed_ref = []
            for child in children:
                r = eval_node(child)
                if r.get('pass'):
                    return {'pass': True}
                failed_evidence.extend(r.get('evidence', []))
                failed_ref.extend(r.get('reference_values', []))
            return {'pass': False, 'evidence': failed_evidence, 'reference_values': failed_ref}

    tree = parse(expression)
    print("Parsed expression tree:", tree)
    return eval_node(tree)
# 预定义函数映射表
PREDEFINED_FUNCTIONS_MAP = {
    'auditPatientSymptoms': audit_patient_symptoms,
    'extract': extract_data,
    'fieldExists': field_exists,
    'fieldMatch': field_match,
    'fieldContains': field_contains,
    'timeAfter': time_after,
    'timeBefore': time_before,
    'timeInRange': time_in_range,
    'limitTime': limit_time,
    'valueComparison': value_comparison,
    'regexMatch': regex_match,
    'hasItemMatch': has_item_match,
    'allItemsMatch': all_items_match,
    'firstValue': get_first_value,
    'lastValue': get_last_value,
    'count': count_values
}
