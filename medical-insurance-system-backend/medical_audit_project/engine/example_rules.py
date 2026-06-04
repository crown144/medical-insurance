# engine/example_rules.py

"""
示例规则代码
这些代码可以直接复制到 Rule 模型的 rule_code 字段中
"""

# 示例1：检查收费项目价格是否超过限制
EXAMPLE_RULE_1 = """
def execute_rule(medical_record: dict, current_item: dict) -> dict:
    \"\"\"检查收费项目单价是否超过100元\"\"\"
    try:
        price_str = current_item.get('项目单价', '0')
        price = float(price_str)
        
        if price > 100.0:
            return {
                "passed": False,
                "reason": f"收费项目单价 {price} 元超过限制 100.0 元",
                "step": "price_check"
            }
        
        return {
            "passed": True,
            "reason": f"收费项目单价 {price} 元在允许范围内",
            "step": "price_check"
        }
    except (ValueError, TypeError) as e:
        return {
            "passed": False,
            "reason": f"无法解析价格: {str(e)}",
            "step": "price_check"
        }
"""

# 示例2：使用 match_field 检查诊断
EXAMPLE_RULE_2 = """
def execute_rule(medical_record: dict, current_item: dict) -> dict:
    \"\"\"检查诊断是否包含指定疾病\"\"\"
    # 使用预定义的 match_field 函数
    target_diseases = ['高血压', '糖尿病', '冠心病']
    
    if match_field(medical_record, '入院记录.诊断', target_diseases):
        return {
            "passed": True,
            "reason": "诊断匹配",
            "step": "diagnosis_check"
        }
    else:
        return {
            "passed": False,
            "reason": f"诊断不包含以下疾病之一: {', '.join(target_diseases)}",
            "step": "diagnosis_check"
        }
"""

# 示例3：使用 check_limit 检查支付时长
EXAMPLE_RULE_3 = """
def execute_rule(medical_record: dict, current_item: dict) -> dict:
    \"\"\"检查支付时长是否超过30天\"\"\"
    # 使用预定义的 check_limit 函数
    if check_limit(medical_record, current_item, 'pay_duration', '30d'):
        return {
            "passed": True,
            "reason": "支付时长在允许范围内",
            "step": "duration_check"
        }
    else:
        return {
            "passed": False,
            "reason": "支付时长超过30天限制",
            "step": "duration_check"
        }
"""

# 示例4：组合多个条件
EXAMPLE_RULE_4 = """
def execute_rule(medical_record: dict, current_item: dict) -> dict:
    \"\"\"组合检查：价格和诊断\"\"\"
    # 检查价格
    price_str = current_item.get('项目单价', '0')
    try:
        price = float(price_str)
        if price > 100.0:
            return {
                "passed": False,
                "reason": f"价格 {price} 元超过限制",
                "step": "combined_check"
            }
    except (ValueError, TypeError):
        return {
            "passed": False,
            "reason": "无法解析价格",
            "step": "combined_check"
        }
    
    # 检查诊断
    if not match_field(medical_record, '入院记录.诊断', ['高血压']):
        return {
            "passed": False,
            "reason": "诊断不匹配",
            "step": "combined_check"
        }
    
    return {
        "passed": True,
        "reason": "所有检查通过",
        "step": "combined_check"
    }
"""

# 示例5：使用 get_value 获取嵌套字段
EXAMPLE_RULE_5 = """
def execute_rule(medical_record: dict, current_item: dict) -> dict:
    \"\"\"使用 get_value 获取病历中的嵌套字段\"\"\"
    # 获取入院日期
    admission_date = get_value(medical_record, '入院记录.入院日期')
    
    if not admission_date:
        return {
            "passed": False,
            "reason": "未找到入院日期",
            "step": "admission_check"
        }
    
    # 获取收费日期
    charge_date = current_item.get('收费日期')
    
    if not charge_date:
        return {
            "passed": False,
            "reason": "未找到收费日期",
            "step": "admission_check"
        }
    
    # 这里可以添加日期比较逻辑
    return {
        "passed": True,
        "reason": f"入院日期: {admission_date}, 收费日期: {charge_date}",
        "step": "admission_check"
    }
"""

