# engine/test_engine.py

"""
规则引擎测试脚本
用于测试重构后的规则引擎功能
"""

import os
import sys
import django
import json

# 设置 Django 环境
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medical_audit_project.settings')
django.setup()

from engine.engine import RuleEngine
from rules.models import Rule
from engine.example_rules import EXAMPLE_RULE_1, EXAMPLE_RULE_2, EXAMPLE_RULE_3


def create_test_rules():
    """创建测试规则"""
    print("=" * 60)
    print("创建测试规则...")
    print("=" * 60)
    
    # 测试规则1：价格检查
    rule1, created = Rule.objects.update_or_create(
        rule_id='test_rule_001',
        defaults={
            'drug_name': '测试药品A',
            'description': '测试规则：检查收费项目价格是否超过100元',
            'rule_code': EXAMPLE_RULE_1,
            'match_field': '收费项目名称',
            'match_value': '测试收费项目',
            'status': True,
            'type': '超限定用药'
        }
    )
    print(f"规则1 {'已创建' if created else '已更新'}: {rule1.rule_id}")
    
    # 测试规则2：诊断检查
    rule2, created = Rule.objects.update_or_create(
        rule_id='test_rule_002',
        defaults={
            'drug_name': '测试药品B',
            'description': '测试规则：检查诊断是否匹配',
            'rule_code': EXAMPLE_RULE_2,
            'match_field': '收费项目名称',
            'match_value': '诊断检查项目',
            'status': True,
            'type': '超限定用药'
        }
    )
    print(f"规则2 {'已创建' if created else '已更新'}: {rule2.rule_id}")
    
    # 测试规则3：时长检查
    rule3, created = Rule.objects.update_or_create(
        rule_id='test_rule_003',
        defaults={
            'drug_name': '测试药品C',
            'description': '测试规则：检查支付时长',
            'rule_code': EXAMPLE_RULE_3,
            'match_field': '收费项目名称',
            'match_value': '时长检查项目',
            'status': True,
            'type': '超限定用药'
        }
    )
    print(f"规则3 {'已创建' if created else '已更新'}: {rule3.rule_id}")
    
    print("\n测试规则创建完成！\n")
    return [rule1, rule2, rule3]


def create_test_patient_data():
    """创建测试病历数据"""
    return {
        "基本信息": {
            "住院号": "TEST001",
            "姓名": "测试患者",
            "出院日期": "2024-01-15"
        },
        "入院记录": {
            "入院日期": "2024-01-01",
            "诊断": ["高血压", "糖尿病"],
            "主诉": "头痛、头晕",
            "现病史": "患者有高血压病史5年"
        },
        "收费报告": [
            {
                "收费项目名称": "测试收费项目",
                "收费项目代码": "TEST001",
                "收费日期": "2024-01-10 10:00:00",
                "项目单价": "150.00",  # 超过100，应该触发违规
                "项目数量": "1",
                "项目费用": "150.00"
            },
            {
                "收费项目名称": "诊断检查项目",
                "收费项目代码": "TEST002",
                "收费日期": "2024-01-05 10:00:00",
                "项目单价": "50.00",
                "项目数量": "1",
                "项目费用": "50.00"
            },
            {
                "收费项目名称": "正常收费项目",
                "收费项目代码": "TEST003",
                "收费日期": "2024-01-08 10:00:00",
                "项目单价": "80.00",  # 不超过100，应该通过
                "项目数量": "1",
                "项目费用": "80.00"
            }
        ]
    }


def test_rule_engine():
    """测试规则引擎"""
    print("=" * 60)
    print("测试规则引擎")
    print("=" * 60)
    
    # 1. 创建测试规则
    test_rules = create_test_rules()
    
    # 2. 创建测试数据
    patient_data = create_test_patient_data()
    print("\n测试病历数据:")
    print(json.dumps(patient_data, ensure_ascii=False, indent=2))
    print()
    
    # 3. 创建引擎并执行测试
    engine = RuleEngine(log_level=10)  # DEBUG 级别
    
    print("=" * 60)
    print("执行审核...")
    print("=" * 60)
    
    results = engine.audit_patient(
        patient_data=patient_data,
        selected_rules=test_rules,
        charge_section_path='收费报告'
    )
    
    # 4. 显示结果
    print("\n" + "=" * 60)
    print("审核结果")
    print("=" * 60)
    print(f"共生成 {len(results)} 条结果\n")
    
    for idx, result in enumerate(results, 1):
        print(f"结果 {idx}:")
        print(f"  规则ID: {result.get('ruleId', 'N/A')}")
        print(f"  是否通过: {result.get('passed', False)}")
        print(f"  是否违规: {result.get('violation', False)}")
        print(f"  原因: {result.get('reason', 'N/A')}")
        print(f"  步骤: {result.get('step', 'N/A')}")
        if result.get('item'):
            item_name = result.get('item', {}).get('收费项目名称', 'N/A')
            print(f"  收费项目: {item_name}")
        print()
    
    # 5. 统计
    passed_count = sum(1 for r in results if r.get('passed', False))
    violation_count = sum(1 for r in results if r.get('violation', False))
    
    print("=" * 60)
    print("统计信息")
    print("=" * 60)
    print(f"总结果数: {len(results)}")
    print(f"通过数: {passed_count}")
    print(f"违规数: {violation_count}")
    print()
    
    return results


def test_single_rule():
    """测试单个规则"""
    print("=" * 60)
    print("测试单个规则执行")
    print("=" * 60)
    
    from engine.rule_executor import RuleExecutor
    
    executor = RuleExecutor()
    
    # 测试数据
    medical_record = {
        "入院记录": {
            "诊断": ["高血压"]
        }
    }
    
    current_item = {
        "收费项目名称": "测试项目",
        "项目单价": "150.00"
    }
    
    # 执行规则
    result = executor.execute_rule(
        rule_code=EXAMPLE_RULE_1,
        medical_record=medical_record,
        current_item=current_item,
        rule_id='test_single'
    )
    
    print("执行结果:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print()
    
    return result


def test_function_registry():
    """测试函数注册器"""
    print("=" * 60)
    print("测试函数注册器")
    print("=" * 60)
    
    from engine.function_registry import get_registry
    
    registry = get_registry()
    
    print("已注册的函数:")
    functions = registry.list_functions()
    for func_name in sorted(functions):
        func = registry.get_function(func_name)
        print(f"  - {func_name}: {func}")
    
    print(f"\n共注册 {len(functions)} 个函数\n")
    
    # 测试获取安全全局命名空间
    test_record = {"test": "data"}
    test_item = {"item": "value"}
    safe_globals = registry.get_safe_globals(test_record, test_item)
    
    print("安全全局命名空间包含:")
    print(f"  - medical_record: {safe_globals.get('medical_record')}")
    print(f"  - current_item: {safe_globals.get('current_item')}")
    print(f"  - get_value: {safe_globals.get('get_value')}")
    print(f"  - match_field: {safe_globals.get('match_field')}")
    print()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='测试规则引擎')
    parser.add_argument('--test', choices=['all', 'engine', 'single', 'registry'], 
                       default='all', help='选择测试类型')
    
    args = parser.parse_args()
    
    try:
        if args.test == 'all':
            test_function_registry()
            test_single_rule()
            test_rule_engine()
        elif args.test == 'engine':
            test_rule_engine()
        elif args.test == 'single':
            test_single_rule()
        elif args.test == 'registry':
            test_function_registry()
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

