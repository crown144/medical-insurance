# 规则引擎重构说明

## 概述

规则引擎已重构，主要变更如下：

1. **移除 Template 机制**：不再使用模板 JSON 配置
2. **直接遍历收费报告**：从病历数据中直接提取"收费报告"模块并遍历
3. **基于 Python 代码的规则**：规则存储为完整的 Python 函数代码字符串
4. **函数注册机制**：通过 FunctionRegistry 管理可用的函数

## 架构变更

### 1. 核心流程

```
病历数据 → 提取收费报告 → 遍历收费项目 → 匹配规则 → 执行规则代码 → 返回结果
```

### 2. 新增组件

- **FunctionRegistry** (`engine/function_registry.py`): 函数注册器，管理可用函数
- **RuleExecutor** (`engine/rule_executor.py`): 规则执行器，使用 exec() 执行规则代码
- **重构的 RuleEngine** (`engine/engine.py`): 新的规则引擎核心

### 3. 数据模型变更

`Rule` 模型新增字段：
- `rule_code`: 存储 Python 函数代码字符串
- `match_field`: 匹配字段名（如 "收费项目名称"）
- `match_value`: 匹配值（如药品名称或代码）

保留字段（向后兼容）：
- `logic_expression`: 旧版逻辑表达式（已弃用）

## 规则代码格式

规则代码必须定义一个名为 `execute_rule` 的函数，函数签名如下：

```python
def execute_rule(medical_record: dict, current_item: dict) -> dict:
    """
    执行规则检查
    
    :param medical_record: 完整病历数据
    :param current_item: 当前收费项
    :return: 结果字典，格式为 {"passed": bool, "reason": str, "step": str}
    """
    # 规则逻辑
    if some_condition:
        return {"passed": False, "reason": "违规原因", "step": "rule_id"}
    return {"passed": True, "reason": "通过", "step": "rule_id"}
```

### 示例规则代码

#### 示例1：检查收费项目价格

```python
def execute_rule(medical_record: dict, current_item: dict) -> dict:
    """检查收费项目单价是否超过限制"""
    price = float(current_item.get('项目单价', 0))
    if price > 100.0:
        return {
            "passed": False,
            "reason": f"收费项目单价 {price} 超过限制 100.0",
            "step": "price_check"
        }
    return {"passed": True, "reason": "价格检查通过", "step": "price_check"}
```

#### 示例2：使用预定义函数检查字段匹配

```python
def execute_rule(medical_record: dict, current_item: dict) -> dict:
    """检查诊断是否匹配"""
    # 使用预定义的 match_field 函数
    if not match_field(medical_record, '入院记录.诊断', ['高血压', '糖尿病']):
        return {
            "passed": False,
            "reason": "诊断不匹配",
            "step": "diagnosis_check"
        }
    return {"passed": True, "reason": "诊断检查通过", "step": "diagnosis_check"}
```

#### 示例3：使用业务函数检查限制

```python
def execute_rule(medical_record: dict, current_item: dict) -> dict:
    """检查支付时长限制"""
    # 使用预定义的 check_limit 函数
    if not check_limit(medical_record, current_item, 'pay_duration', '30d'):
        return {
            "passed": False,
            "reason": "支付时长超过30天",
            "step": "duration_check"
        }
    return {"passed": True, "reason": "时长检查通过", "step": "duration_check"}
```

## 可用函数

### 原子函数 (atomic.py)

- `match_field(record: dict, path: str, target_values: list) -> bool`: 检查字段值是否匹配
- `compare_value(record: dict, path: str, operator: str, threshold: float) -> bool`: 数值比较
- `llm_predicate(record: dict, context_fields: list, condition: str) -> bool`: LLM 语义判断

### 业务函数 (business.py)

- `check_limit(record: dict, current_item: dict, limit_type: str, threshold: str) -> bool`: 检查各种限制

### 工具函数 (utils.py)

- `get_value(data: dict, path: str) -> Any`: 根据路径从字典中取值

## 使用方式

### 1. 创建规则

在 Django Admin 或通过 API 创建规则时，设置以下字段：

- `rule_id`: 规则ID（唯一）
- `drug_name`: 药品名称（用于匹配，可选）
- `match_field`: 匹配字段名（如 "收费项目名称"）
- `match_value`: 匹配值（如 "阿司匹林"）
- `rule_code`: Python 函数代码字符串
- `status`: 是否启用
- `type`: 规则类型（如 "超限定用药"）

### 2. 调用规则引擎

```python
from engine.engine import RuleEngine
from rules.models import Rule

# 创建引擎实例
engine = RuleEngine()

# 获取规则（可选，不传则使用所有启用的规则）
selected_rules = Rule.objects.filter(type='超限定用药', status=True)

# 执行审核
results = engine.audit_patient(
    patient_data=patient_json,
    selected_rules=selected_rules,
    charge_section_path='收费报告'  # 可选，默认为 '收费报告'
)

# 处理结果
for result in results:
    if not result.get('passed'):
        print(f"违规: {result.get('reason')}")
        print(f"规则ID: {result.get('ruleId')}")
```

### 3. 结果格式

```python
{
    "passed": bool,           # 是否通过
    "reason": str,            # 原因说明
    "step": str,              # 步骤标识
    "ruleId": str,            # 规则ID
    "ruleDescription": str,   # 规则描述
    "violation": bool,        # 是否违规（与 passed 相反）
    "item": dict,             # 当前收费项
    "highlights": [           # 高亮信息（仅违规时）
        {
            "field_path": str,
            "highlighted_text": str
        }
    ]
}
```

## 迁移指南

### 从旧系统迁移

1. **数据迁移**：需要为现有规则添加 `rule_code` 字段
2. **规则转换**：将 `logic_expression` 转换为 `rule_code` 格式
3. **测试验证**：确保新规则代码能正确执行

### 兼容性

- 旧版 `logic_expression` 字段保留，但不再使用
- `AuditTemplate` 模型保留，但不再被规则引擎使用
- 结果格式兼容旧版（支持 `violation` 和 `passed` 两种格式）

## 注意事项

1. **安全性**：规则代码通过 `exec()` 执行，已限制危险函数，但仍需谨慎
2. **性能**：每条收费项目都会匹配并执行规则，注意优化规则代码
3. **错误处理**：规则代码执行出错会返回错误结果，不会中断整个审核流程

## 文件结构

```
engine/
├── __init__.py
├── engine.py              # 重构后的规则引擎核心
├── rule_executor.py       # 规则执行器
├── function_registry.py   # 函数注册器
├── atomic.py             # 原子函数
├── business.py           # 业务函数
├── utils.py              # 工具函数
└── README_REFACTOR.md    # 本文档
```

