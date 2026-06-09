"""
测试脚本：生成不同结构的模拟飞检Excel文件，验证自动识别能力

运行方式:
    cd medical_audit_project
    python -m feijian.tests.test_analyzer
"""

import os
import sys
import tempfile
from pathlib import Path

import pandas as pd


def create_test_excel_variants(output_dir: str):
    """
    生成3种不同结构的飞检Excel文件，用于测试识别能力
    """
    data = {
        '住院号': ['ZY010000465188', 'ZY010000472172', 'ZY010000472994'],
        '患者姓名': ['张三', '李四', '王五'],
        '医院名称': ['湖南省人民医院', '长沙市中心医院', '株洲市第一人民医院'],
        '入院日期': ['2026-01-15', '2026-02-20', '2026-03-10'],
        '出院日期': ['2026-01-28', '2026-03-05', '2026-03-22'],
        '违规类型': ['分解住院', '过度检查', '虚假住院'],
        '违规描述': ['将一次住院拆分为两次', '无指征做全套CT检查', '实际未住院伪造记录'],
        '涉及金额': [23500.00, 8600.00, 45200.00],
        '检查机构': ['国家医保局飞检组', '湖南省医保局', '湖南省医保局'],
        '检查日期': ['2026-05-10', '2026-05-20', '2026-05-18'],
    }
    df = pd.DataFrame(data)
    df.to_excel(os.path.join(output_dir, 'variant1_标准格式.xlsx'), index=False)

    # 变体2: 英文/混合列名
    data2 = {
        'Patient ID': ['HN20260501001', 'HN20260501002', 'HN20260501003'],
        'Name': ['Alice Chen', 'Bob Wang', 'Carol Li'],
        'Hospital': ['Hunan Provincial Hospital', 'Changsha Central Hospital', 'Zhuzhou No.1 Hospital'],
        'Admission': ['2026-04-15', '2026-04-20', '2026-04-10'],
        'Discharge': ['2026-04-28', '2026-05-05', '2026-04-22'],
        'Issue Type': ['Decomposed hospitalization', 'Excessive examination', 'False hospitalization'],
        'Description': ['Admission split into two', 'Unnecessary full CT scan', 'Fake medical records'],
        'Amount': [23500.00, 8600.00, 45200.00],
        'Audit Org': ['National Audit Team', 'Hunan Provincial Audit', 'Hunan Provincial Audit'],
        'Audit Date': ['2026-05-10', '2026-05-20', '2026-05-18'],
    }
    df2 = pd.DataFrame(data2)
    df2.to_excel(os.path.join(output_dir, 'variant2_英文格式.xlsx'), index=False)

    # 变体3: 不规范的列名 + 额外列
    data3 = {
        '编号': ['ZY010000465188', 'ZY010000472172', 'ZY010000472994'],
        '病人': ['张三', '李四', '王五'],
        '定点医药机构名称': ['湖南省人民医院', '长沙市中心医院', '株洲市第一人民医院'],
        '住院开始时间': ['2026-01-15', '2026-02-20', '2026-03-10'],
        '出院时间': ['2026-01-28', '2026-03-05', '2026-03-22'],
        '违规问题大类': ['分解住院', '过度检查', '虚假住院'],
        '问题具体情况': ['将一次住院拆分为两次套取基金', '无指征做全套CT检查', '实际未住院，伪造住院记录套取基金'],
        '核定违规金额(元)': [23500.00, 8600.00, 45200.00],
        '审计单位': ['国家医保局飞检组', '湖南省医保局', '湖南省医保局'],
        '审计日期': ['2026-05-10', '2026-05-20', '2026-05-18'],
        '备注': ['已确认', '待复核', '已移交公安'],
        '联系电话': ['13800138001', '13800138002', '13800138003'],
    }
    df3 = pd.DataFrame(data3)
    df3.to_excel(os.path.join(output_dir, 'variant3_不规范格式.xlsx'), index=False)

    print(f"生成了3个测试Excel文件到: {output_dir}")


def test_analyzer():
    """测试 Excel 列识别器"""
    # 确保 Django 环境已加载
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medical_audit_project.settings')
    django.setup()

    from feijian.services.excel_analyzer import ExcelColumnAnalyzer

    # 创建临时目录
    tmp_dir = tempfile.mkdtemp(prefix='feijian_test_')
    create_test_excel_variants(tmp_dir)

    analyzer = ExcelColumnAnalyzer(enable_llm=False)

    for variant in ['variant1_标准格式.xlsx', 'variant2_英文格式.xlsx', 'variant3_不规范格式.xlsx']:
        file_path = os.path.join(tmp_dir, variant)
        print(f"\n{'='*60}")
        print(f"测试: {variant}")
        print(f"{'='*60}")

        result = analyzer.analyze(file_path)

        print(f"列名: {result.columns}")
        print(f"\n识别结果:")
        for m in result.mappings:
            print(f"  {m.field_label}({m.field_key}) → {m.column_name} "
                  f"[置信度: {m.confidence:.0%}, 方法: {m.method}]")

        if result.unmapped_fields:
            print(f"\n未匹配字段: {result.unmapped_fields}")
        if result.unmapped_columns:
            print(f"未识别列: {result.unmapped_columns}")

    # 清理
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == '__main__':
    test_analyzer()