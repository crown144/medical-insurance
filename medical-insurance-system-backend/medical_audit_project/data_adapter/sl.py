# 医疗记录API使用示例
# 只需要 sy.py 和 medical_api.py 两个文件

from medical_api import (
    get_patient_json_data,
    get_batch_patients_json_data,
    save_patient_json_to_file,
    test_database_connection,
    MedicalAPI
)
import json

def 示例1_测试数据库连接():
    """
    示例1：测试数据库连接
    """
    print("=== 示例1：测试数据库连接 ===")
    
    # 使用sy.py中的默认数据库配置
    result = test_database_connection()
    
    if result["success"]:
        print("✓ 数据库连接成功")
    else:
        print(f"✗ 数据库连接失败: {result['message']}")
    
    return result["success"]

def 示例2_获取单个患者数据():
    """
    示例2：获取单个患者的JSON数据（不保存文件）
    """
    print("\n=== 示例2：获取单个患者JSON数据 ===")
    
    # 使用sy.py中的默认住院号
    inhos_no = "ZY010000483837"
    
    # 获取患者数据
    result = get_patient_json_data(
        inhos_no=inhos_no,
        modules=["诊断", "病理", "检查"],  # 指定需要的模块
        icd10_ranges=["I20-I25"]  # 可选：指定ICD10范围
    )
    
    if result["success"]:
        print(f"✓ 成功获取患者 {inhos_no} 的数据")
        json_data = result["json_data"]
        
        # 显示数据概览
        print("数据概览:")
        for module_name, module_data in json_data.items():
            if isinstance(module_data, list):
                print(f"  {module_name}: {len(module_data)} 条记录")
            else:
                print(f"  {module_name}: {type(module_data).__name__}")
        
        # 可以直接使用json_data进行后续处理
        return json_data
    else:
        print(f"✗ 获取患者数据失败: {result['error']}")
        return None

def 示例3_批量获取患者数据():
    """
    示例3：批量获取多个患者的JSON数据
    """
    print("\n=== 示例3：批量获取患者数据 ===")
    
    # 患者住院号列表
    inhos_list = ["ZY010000483837", "ZY010000483838", "ZY010000483839"]
    
    # 批量获取数据
    result = get_batch_patients_json_data(
        inhos_list=inhos_list,
        modules=["诊断", "病理"]
    )
    
    print(f"批量处理结果:")
    print(f"  总数: {result['total']}")
    print(f"  成功: {result['success_count']}")
    print(f"  失败: {result['failed_count']}")
    
    # 处理成功的患者数据
    if result['success_count'] > 0:
        print("\n成功获取的患者:")
        for patient_data in result['patients_data']:
            inhos_no = patient_data['inhos_no']
            json_data = patient_data['json_data']
            print(f"  患者 {inhos_no}: {len(json_data)} 个模块")
    
    # 处理失败的记录
    if result['failed_count'] > 0:
        print("\n失败的记录:")
        for failed_record in result['failed_records']:
            print(f"  患者 {failed_record['inhos_no']}: {failed_record['error']}")
    
    return result['patients_data']

def 示例4_保存数据到文件():
    """
    示例4：获取患者数据并保存到文件
    """
    print("\n=== 示例4：保存数据到文件 ===")
    
    inhos_no = "ZY010000483837"
    output_dir = "./output"  # 输出目录

    
    # 获取数据并保存到文件
    result = save_patient_json_to_file(
        inhos_no=inhos_no,
        output_dir=output_dir,
        modules=["diagnosis", "pathology", "examination"]
    )
    
    if result["success"]:
        print(f"✓ 数据已保存到文件: {result['file_path']}")
        return result['file_path']
    else:
        print(f"✗ 保存失败: {result['error']}")
        return None

def 示例5_使用API类():
    """
    示例5：直接使用API类进行更复杂的操作
    """
    print("\n=== 示例5：使用API类 ===")
    
    # 创建API实例
    api = MedicalAPI()
    
    # 测试数据库连接
    conn_result = api.test_database_connection()
    if not conn_result["success"]:
        print(f"数据库连接失败: {conn_result['message']}")
        return
    
    print("数据库连接成功")
    
    # 获取可用模块列表
    modules = api.get_available_modules()
    print(f"可用模块: {modules[:5]}...")  # 显示前5个模块
    
    # 获取多个患者的数据
    patients = ["ZY010000483837"]
    all_data = []
    
    for inhos_no in patients:
        result = api.get_patient_json_data(
            inhos_no=inhos_no,
            modules=["diagnosis", "pathology"]
        )
        
        if result["success"]:
            all_data.append({
                "patient_id": inhos_no,
                "data": result["json_data"]
            })
            print(f"✓ 获取患者 {inhos_no} 数据成功")
        else:
            print(f"✗ 获取患者 {inhos_no} 数据失败: {result['error']}")
    
    print(f"总共获取了 {len(all_data)} 个患者的数据")
    return all_data

def 示例6_自定义数据库配置():
    """
    示例6：使用自定义数据库配置
    """
    print("\n=== 示例6：自定义数据库配置 ===")
    
    from source_db import get_source_db_config

    custom_db_config = get_source_db_config()
    
    # 测试自定义配置
    result = test_database_connection(custom_db_config)
    
    if result["success"]:
        print("✓ 自定义数据库配置连接成功")
        
        # 使用自定义配置获取数据
        data_result = get_patient_json_data(
            inhos_no="ZY010000483837",
            modules=["diagnosis"],
            db_config=custom_db_config
        )
        
        if data_result["success"]:
            print("✓ 使用自定义配置获取数据成功")
        else:
            print(f"✗ 获取数据失败: {data_result['error']}")
    else:
        print(f"✗ 自定义数据库配置连接失败: {result['message']}")

def 示例7_显示JSON前100行():
    """
    示例7：获取ZY010000483837转换后病历的前100行
    """
    print("\n=== 示例7：显示JSON前100行 ===")
    
    # 获取患者数据
    result = get_patient_json_data(
        inhos_no="ZY010000483837"
    )
    
    if not result["success"]:
        print(f"获取数据失败: {result['error']}")
        return
    
    # 将JSON数据转换为格式化的字符串
    json_string = json.dumps(result["json_data"], ensure_ascii=False, indent=2)
    
    # 按行分割并显示前100行
    lines = json_string.split('\n')
    
    for i, line in enumerate(lines[:100], 1):
        print(f"{i:3d}: {line}")
    
    return result["json_data"]

if __name__ == "__main__":
    print("医疗记录API使用示例")
    print("=" * 50)
    
    try:
        # 首先测试数据库连接
        if 示例1_测试数据库连接():
            # 如果连接成功，运行其他示例
            示例2_获取单个患者数据()
            示例3_批量获取患者数据()
            示例4_保存数据到文件()
            示例5_使用API类()
            示例6_自定义数据库配置()
            示例7_显示JSON前100行()
        else:
            print("\n数据库连接失败，请检查 SOURCE_DB_* 环境变量")
        
        print("\n=== 所有示例运行完成 ===")
        
    except Exception as e:
        print(f"运行示例时出错: {e}")
        import traceback
        traceback.print_exc()
