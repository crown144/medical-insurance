import os
import sys
import json

def main():
    # 将项目根目录加入路径，方便导入 settings 与应用模块
    project_root = os.path.dirname(os.path.dirname(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # 初始化Django环境
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medical_audit_project.settings')
    try:
        import django
        django.setup()
    except Exception as e:
        print(f"[ERROR] Django 初始化失败: {e}")
        sys.exit(1)

    # 解析输入文件路径
    if len(sys.argv) > 1:
        json_path = sys.argv[1]
    else:
        json_path = os.path.join('mock_patient_data', 'ZY010000510917.json')

    if not os.path.exists(json_path):
        print(f"[ERROR] 病例JSON文件不存在: {json_path}")
        sys.exit(1)

    # 加载病例数据
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            patient_json = json.load(f)
    except Exception as e:
        print(f"[ERROR] 加载JSON失败: {e}")
        sys.exit(1)

    # 运行检测
    try:
        from repeat_charging.integration import detect_enhanced_duplicate_charges
        result = detect_enhanced_duplicate_charges(patient_json)
    except Exception as e:
        print(f"[ERROR] 检测执行失败: {e}")
        sys.exit(1)

    violations = result.get('violations', [])
    summary = result.get('summary', {})

    print("=== 检测结果摘要 ===")
    print(f"总违规数: {len(violations)}")
    if summary:
        print(f"摘要: {summary}")

    father_child = [v for v in violations if v.get('rule', {}).get('type') == '重复收费-父子']
    print(f"父子重复违规数: {len(father_child)}")

    if father_child:
        print("=== 示例父子违规 ===")
        v = father_child[0]
        rule = v.get('rule', {})
        item = v.get('item', {})
        print(f"rule_id: {rule.get('rule_id')}")
        print(f"type: {rule.get('type')}")
        print(f"drug_name: {rule.get('drug_name')}")
        print(f"重复日期: {item.get('重复日期')}")
        print(f"父项目: {item.get('父项目名称')}({item.get('父项目代码')})")
        print(f"子项目: {item.get('子项目名称')}({item.get('子项目代码')})")
        print(f"总金额: {item.get('总金额')}")
        print(f"父项记录数/子项记录数: {item.get('父项记录数')}/{item.get('子项记录数')}")

    print("=== 结束 ===")


if __name__ == '__main__':
    main()