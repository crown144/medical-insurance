# 医疗记录处理API - 简化版本
# 只需要sy.py文件即可使用

import sys
import os
from typing import Dict, List, Any, Optional
import traceback

# 已根据文件结构修改导入路径，确保sy.py在同一目录下
try:
    from .sy import MedicalDataProcessor, MedicalRecordConverter, DB_CONFIG
except ImportError as e:
    print(f"错误：无法导入sy.py中的类，请确保sy.py文件在同一目录下。错误详情：{e}")
    sys.exit(1)

class MedicalAPI:
    """
    医疗记录处理API接口
    封装sy.py的功能，提供简单易用的接口
    """
    
    def __init__(self, db_config=None):
        """
        初始化API
        
        Args:
            db_config: 数据库配置，如果不提供则使用sy.py中的默认配置
        """
        self.db_config = db_config or DB_CONFIG
        self.processor = None
        self.converter = MedicalRecordConverter()
        
    def get_patient_json_data(self, inhos_no: str, modules: List[str] = None, 
                             icd10_ranges: List[str] = None) -> Dict[str, Any]:
        """
        获取单个患者的JSON数据（不保存文件）
        
        Args:
            inhos_no: 住院号
            modules: 需要处理的模块列表，如 ["pathology", "diagnosis"]
            icd10_ranges: ICD10范围列表，如 ["I20-I25"]
            
        Returns:
            {
                "success": bool,
                "json_data": dict,  # 成功时包含JSON数据
                "error": str        # 失败时包含错误信息
            }
        """
        try:
            # 创建处理器实例
            processor = MedicalDataProcessor(inhos_no)
            
            # 处理模块数据
            # 如果modules为None或空列表，传递None给process_modules使用默认模块
            modules_to_process = modules if modules else None
            json_data = processor.process_modules(modules_to_process)
            
            # 如果指定了ICD10范围，进行过滤
            if icd10_ranges and json_data:
                # 提取主要ICD10编码
                main_icd10 = self._extract_main_icd10_code(json_data)
                if main_icd10:
                    # 检查是否在指定范围内
                    if not self._is_icd10_in_range(main_icd10, icd10_ranges):
                        return {
                            "success": False,
                            "error": f"患者ICD10编码 {main_icd10} 不在指定范围 {icd10_ranges} 内"
                        }
            
            return {
                "success": True,
                "json_data": json_data
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    # --- 新增方法：获取最终格式的数据 ---
    def get_patient_final_json_data(self, inhos_no: str) -> Dict[str, Any]:
        """
        获取单个患者【最终格式】的JSON数据（包含重命名等完整处理流程）
        
        Args:
            inhos_no: 住院号
            
        Returns:
            {
                "success": bool,
                "json_data": dict,  # 成功时包含最终格式的JSON数据
                "error": str        # 失败时包含错误信息
            }
        """
        try:
            # 创建sy.py中的核心处理器实例
            processor = MedicalDataProcessor(inhos_no)
            
            # 调用最完整的处理函数，但设置不输出文件
            final_data = processor.process_all_and_export(output_file=None)
            
            # 检查是否因数据不完整而提前终止
            if final_data.get("提前终止"):
                return {
                    "success": False,
                    "error": final_data.get("终止原因", "处理因记录不完整而终止")
                }

            return {
                "success": True,
                "json_data": final_data
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"处理时发生严重错误: {e}\n{traceback.format_exc()}"
            }
            
    def get_batch_patients_json_data(self, inhos_list: List[str], 
                                   modules: List[str] = None,
                                   icd10_ranges: List[str] = None) -> Dict[str, Any]:
        """
        批量获取患者JSON数据（不保存文件）
        
        Args:
            inhos_list: 住院号列表
            modules: 需要处理的模块列表
            icd10_ranges: ICD10范围列表
            
        Returns:
            {
                "total": int,
                "success_count": int,
                "failed_count": int,
                "patients_data": [  # 成功的患者数据
                    {
                        "inhos_no": str,
                        "json_data": dict
                    }
                ],
                "failed_records": [  # 失败的记录
                    {
                        "inhos_no": str,
                        "error": str
                    }
                ]
            }
        """
        total = len(inhos_list)
        success_count = 0
        failed_count = 0
        patients_data = []
        failed_records = []
        
        for inhos_no in inhos_list:
            result = self.get_patient_json_data(inhos_no, modules, icd10_ranges)
            
            if result["success"]:
                success_count += 1
                patients_data.append({
                    "inhos_no": inhos_no,
                    "json_data": result["json_data"]
                })
            else:
                failed_count += 1
                failed_records.append({
                    "inhos_no": inhos_no,
                    "error": result["error"]
                })
        
        return {
            "total": total,
            "success_count": success_count,
            "failed_count": failed_count,
            "patients_data": patients_data,
            "failed_records": failed_records
        }
    
    def save_patient_json_to_file(self, inhos_no: str, output_dir: str,
                                 modules: List[str] = None,
                                 icd10_ranges: List[str] = None) -> Dict[str, Any]:
        """
        获取患者数据并保存到文件
        
        Args:
            inhos_no: 住院号
            output_dir: 输出目录
            modules: 需要处理的模块列表
            icd10_ranges: ICD10范围列表
            
        Returns:
            {
                "success": bool,
                "file_path": str,  # 成功时包含文件路径
                "error": str       # 失败时包含错误信息
            }
        """
        try:
            # 获取JSON数据
            result = self.get_patient_json_data(inhos_no, modules, icd10_ranges)
            
            if not result["success"]:
                return result
            
            # 保存到文件
            import json
            os.makedirs(output_dir, exist_ok=True)
            file_path = os.path.join(output_dir, f"{inhos_no}.json")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(result["json_data"], f, ensure_ascii=False, indent=2)
            
            return {
                "success": True,
                "file_path": file_path
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _extract_main_icd10_code(self, json_data: dict) -> Optional[str]:
        """
        从JSON数据中提取主要ICD10编码
        """
        try:
            # 从诊断模块中提取ICD10编码
            diagnoses = json_data.get("诊断", [])
            if diagnoses and isinstance(diagnoses, list) and len(diagnoses) > 0:
                first_diagnosis = diagnoses[0]
                if isinstance(first_diagnosis, dict):
                    icd10_code = first_diagnosis.get("ICD10编码", "")
                    if icd10_code and icd10_code != "xxx":
                        # 提取主要编码（去掉小数点后的部分）
                        return icd10_code.split('.')[0] if '.' in icd10_code else icd10_code
            return None
        except Exception:
            return None
    
    def _is_icd10_in_range(self, icd10_code: str, ranges: List[str]) -> bool:
        """
        检查ICD10编码是否在指定范围内
        """
        try:
            for range_str in ranges:
                if '-' in range_str:
                    start, end = range_str.split('-')
                    if start <= icd10_code <= end:
                        return True
                else:
                    if icd10_code.startswith(range_str):
                        return True
            return False
        except Exception:
            return False
    
    def test_database_connection(self) -> Dict[str, Any]:
        """
        测试数据库连接
        
        Returns:
            {
                "success": bool,
                "message": str
            }
        """
        try:
            import pymysql
            connection = pymysql.connect(**self.db_config)
            connection.close()
            return {
                "success": True,
                "message": "数据库连接成功"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"数据库连接失败: {e}"
            }
    
    def get_available_modules(self) -> List[str]:
        """
        获取可用的医疗记录模块列表
        """
        return [
            "pathology",      # 病理
            "doctor_orders",  # 医嘱
            "nursing",        # 护理记录
            "examination",    # 检查
            "lab_test",       # 检验
            "diagnosis",      # 诊断
            "medication",     # 用药
            "surgery",        # 手术记录
            "charges",        # 收费
            "insurance",      # 医保
            "admission",      # 入院记录
            "first_course",   # 首次病程记录
            "senior_rounds",  # 上级医师查房记录
            "daily_course",   # 日常病程记录
            "discharge",      # 出院记录
            "assessment",     # 在院评估单
            "surgery_detail"  # 手术记录详情
        ]

# --- 便捷函数 ---

def get_patient_json_data(inhos_no: str, modules: List[str] = None,
                         icd10_ranges: List[str] = None,
                         db_config: Dict = None) -> Dict[str, Any]:
    """
    便捷函数：获取单个患者的JSON数据
    
    Args:
        inhos_no: 住院号
        modules: 需要处理的模块列表
        icd10_ranges: ICD10范围列表
        db_config: 数据库配置（可选，默认使用sy.py中的配置）
        
    Returns:
        包含成功状态和JSON数据的字典
    """
    api = MedicalAPI(db_config)
    return api.get_patient_json_data(inhos_no, modules, icd10_ranges)

# --- 新增便捷函数 ---
def get_patient_final_json_data(inhos_no: str, db_config: Dict = None) -> Dict[str, Any]:
    """
    便捷函数：获取单个患者的【最终格式】JSON数据
    
    Args:
        inhos_no: 住院号
        db_config: 数据库配置（可选）
        
    Returns:
        包含成功状态和最终格式JSON数据的字典
    """
    api = MedicalAPI(db_config)
    return api.get_patient_final_json_data(inhos_no)

def get_batch_patients_json_data(inhos_list: List[str], modules: List[str] = None,
                                icd10_ranges: List[str] = None,
                                db_config: Dict = None) -> Dict[str, Any]:
    """
    便捷函数：批量获取患者JSON数据
    
    Args:
        inhos_list: 住院号列表
        modules: 需要处理的模块列表
        icd10_ranges: ICD10范围列表
        db_config: 数据库配置（可选，默认使用sy.py中的配置）
        
    Returns:
        包含批量处理结果的字典
    """
    api = MedicalAPI(db_config)
    return api.get_batch_patients_json_data(inhos_list, modules, icd10_ranges)

def save_patient_json_to_file(inhos_no: str, output_dir: str,
                             modules: List[str] = None,
                             icd10_ranges: List[str] = None,
                             db_config: Dict = None) -> Dict[str, Any]:
    """
    便捷函数：获取患者数据并保存到文件
    
    Args:
        inhos_no: 住院号
        output_dir: 输出目录
        modules: 需要处理的模块列表
        icd10_ranges: ICD10范围列表
        db_config: 数据库配置（可选，默认使用sy.py中的配置）
        
    Returns:
        包含成功状态和文件路径的字典
    """
    api = MedicalAPI(db_config)
    return api.save_patient_json_to_file(inhos_no, output_dir, modules, icd10_ranges)

def test_database_connection(db_config: Dict = None) -> Dict[str, Any]:
    """
    便捷函数：测试数据库连接
    
    Args:
        db_config: 数据库配置（可选，默认使用sy.py中的配置）
        
    Returns:
        包含连接测试结果的字典
    """
    api = MedicalAPI(db_config)
    return api.test_database_connection()

if __name__ == "__main__":
    # 简单测试
    print("医疗记录处理API - 测试")
    print("=" * 30)
    
    # 测试数据库连接
    conn_result = test_database_connection()
    print(f"数据库连接测试: {conn_result}")
    
    if conn_result["success"]:
        # 测试获取患者数据
        test_inhos_no = "ZY010000483837"  # 使用sy.py中的默认住院号
        result = get_patient_json_data(
            inhos_no=test_inhos_no,
            modules=["诊断", "病理"]
        )
        
        if result["success"]:
            print(f"✓ 成功获取患者 {test_inhos_no} 的数据")
            json_data = result["json_data"]
            for module_name, module_data in json_data.items():
                if isinstance(module_data, list):
                    print(f"  {module_name}: {len(module_data)} 条记录")
                else:
                    print(f"  {module_name}: {type(module_data).__name__}")
        else:
            print(f"✗ 获取患者数据失败: {result['error']}")
    else:
        print("数据库连接失败，无法进行测试")
