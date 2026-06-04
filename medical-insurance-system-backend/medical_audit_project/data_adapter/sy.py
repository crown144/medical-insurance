import pandas as pd
from sqlalchemy import create_engine
import pymysql
from datetime import datetime
import json
import sys
import os
import requests
from typing import Dict, List, Any, Optional, Union
import re
import glob

# 数据库配置
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "hainan",
    "database": "sys",
    "ssl": {"ssl": {}}
}

# 默认住院号 ZY010000512354
DEFAULT_INHOS_NO = "ZY010000483837"   
FIXED_OUTPUT_DIR = "/home/user/病历分析结果"

def delete_old_files_for_inhos_no(result_dir, inhos_no, current_file):
    """
    删除同住院号的旧文件，保留当前生成的文件
    
    Args:
        result_dir: 结果目录路径
        inhos_no: 住院号
        current_file: 当前生成的文件路径
    """
    try:
        # 获取当前文件名
        current_filename = os.path.basename(current_file)
        
        # 查找同住院号的所有文件
        pattern = os.path.join(result_dir, f"patient_{inhos_no}_*.json")
        matching_files = glob.glob(pattern)
        
        deleted_count = 0
        for file_path in matching_files:
            filename = os.path.basename(file_path)
            # 如果不是当前生成的文件，则删除
            if filename != current_filename:
                try:
                    os.remove(file_path)
                    print(f"    已删除旧文件: {filename}")
                    deleted_count += 1
                except Exception as e:
                    print(f"    删除文件 {filename} 时出错: {e}")
        
        if deleted_count > 0:
            print(f"    共删除 {deleted_count} 个同住院号的旧文件")
        else:
            print(f"    未发现同住院号的旧文件")
            
    except Exception as e:
        print(f"    删除旧文件时出错: {e}")

class MedicalRecordConverter:
    def __init__(self):
        # 各模块字段映射
        self.module_mappings = {
            "病理": {"住院流水号": "INHOS_NO", "临床诊断": "DIAG_DSCPT", "病理类型": "PTHLG_EXAM_TP_NM",
                     "病理诊断结果": "PTHLG_DIAG", "镜下所见": "EXAM_RPT_RSLT_MICSCPC",
                     "肉眼所见": "EXAM_RPT_RSLT_MACSCPC", "报告内容": "",
                     "免疫组化": "IMNHSTCHMCL_DTCT_RSLT", "检查时间": "EXAM_DT",
                     "报告时间": "RPT_DT"},
            "医嘱": {"医嘱id": "ODR_NO", "住院流水号": "INHOS_NO", "医嘱类型名称": "ODR_ITM_TP_NM",
                     "医嘱类型": "ODR_ITM_TP_CD", "医嘱时间": "ODR_OPN_DT_TM", "状态": "ODR_EXEC_STTS_NM",
                     "停止时间": "ODR_STP_DT_TM", "医嘱ID": "ODR_SQNC_NO", "医嘱项类别": "ODR_ITM_CD",
                     "项目名称": "ODR_ITM_NM", "医嘱项规格": "DRG_SPCF", "单次剂量数量": "DRG_USE_ONCE_DOSG",
                     "单次给药数量": "DRG_USE_TOT_DOSG", "给药途径": "DOS_RUT_NM", "给药频次": "DRG_USE_FRQ_NM", "申请时间": "ODR_OPN_DT_TM"},
            "检查": {"住院流水号": "INHOS_NO", "检查ID": "EXAM_RCD_NO", "检查项目": "EXAM_ITM_TP_NM",
                     "检查部位": "EXAM_PRT_NM", "检查子类型": "EXAM_ITM_NM", "检查内容": "EXAM_RPT_RSLT_OBJCT",
                     "图像分析": "EXAM_RPT_RSLT_SBJCT", "检查描述": "EXAM_PRCS_DSCPT", "申请时间": "APL_DT_TM",
                     "检查时间": "EXAM_DT", "报告时间": "EXAM_RPT_DT"},
            "检验": {"住院流水号": "INHOS_NO", "检验ID": "TEST_RCD_NO", "检验项目": "TEST_ITM_NM",
                    "检测值": "TEST_RSLT_VLU", "单位": "TEST_RSLT_VLU_UNT",
                     "正常值上限": "NML_VLU_MAX", "正常值下限": "NML_VLU_MIN", "申请时间": "APL_DT_TM",
                     "检验时间": "TEST_DT", "报告时间": "TEST_RPT_DT", "检验详情": "",
                     "院内检验子项目代码": "TEST_CHD_ITM_CD", "院内检验子项目名称": "TEST_CHD_ITM_NM"},
            "诊断": {"住院流水号": "INHOS_NO", "ICD10编码": "DIAG_ICD10_CD", "诊断编号": "DIAG_RCD_NO","ICD10名称": "DIAG_ICD10_NM",
                     "诊断时间": "DIAG_DT", "诊断名称": "DIAG_DSCPT", "诊断类型": "DIAG_CGY_NM",
                     "院内诊断编码": "DIAG_CD"},
            "诊断信息": {"住院流水号": "INHOS_NO", "诊断名称": "DIAG_NM", "ICD编码": "DIAG_CD", 
                       "诊断排序": "DIAG_SRL_NO", "主诊断标志": "MAIN_DIAG_FLG"},
            "医保": {
                "医疗保险类别代码": "MDCR_CGY_CD",
                "医疗保险类别名称": "MDCR_CGY_NM",
                "性别": "GDR_NM", # 将从护理记录中获取
                "年龄": "AGE",    # 将从护理记录中获取
                "年龄单位": "AGE_UNT", # 将从护理记录中获取
            },
            "收费": {
                "住院号": "INHOS_NO",
                "收费项目名称": "CHRG_ITM_NM",
                "收费项目代码": "CHRG_ITM_CD",
                "收费日期": "CHRG_DT",
                "项目数量": "ITM_QTY",
                "项目单价": "ITM_UNT_PRICE",
                "项目单位": "ITM_UNT",
                "项目费用": "ITM_FEE",
                "费用类别": "FEE_CGY_NM",
                "ORDER_NO": "ORDER_NO",
                "ORDER_ITEM_CODE": "ORDER_ITEM_CODE",
            },
            "用药信息": {
                # 三级结构：用药信息 -> 药品信息 -> 第n次开药
                # 字段将在专门的处理方法中构建
                "药品名": "CHRG_ITM_NM",  # 来自FACT_INHOS_FEE_DTL
                "药品类别": "FEE_CGY_NM",  # 来自FACT_INHOS_FEE_DTL
                "药品通用名": "DRG_CMN_NM",  # 来自DIM_DRG_INFMT
                "药品国家编码": "MDCR_DRG_CD_CTRY",  # 来自DIM_DRG_INFMT
                "药品收费时间": "CHRG_DT",  # 来自FACT_INHOS_FEE_DTL
                "给药目的": "DOS_PPS",  # 来自FACT_INHOS_ODR_INFMT
                "药物使用总剂量": "DRG_USE_TOT_DOSG",  # 来自FACT_INHOS_ODR_INFMT
                "药品使用总剂量单位": "DRG_USE_TOT_DOSG_UNT",  # 来自FACT_INHOS_ODR_INFMT
                "药物使用次剂量": "DRG_USE_ONCE_DOSG",  # 来自FACT_INHOS_ODR_INFMT
                "药品使用次剂量单位": "DRG_USE_ONCE_DOSG_UNT",  # 来自FACT_INHOS_ODR_INFMT
                "药品使用频次名称": "DRG_USE_FRQ_NM"  # 来自FACT_INHOS_ODR_INFMT
            },
            "手术记录": {
                "住院流水号": "INHOS_NO",
                "创建时间": "CRT_TM",  # 修改为CRT_TM以与TEST1.py保持一致
                "手术时间": "OPRT_DT_TM",
                "手术名称": "OPRT_NM",
                "术前诊断": "POPRT_DIAG_NM",
                "术中诊断": "OPRT_DIAG_NM",  # 添加术中诊断字段
                "术后诊断": "OPRT_AFTR_DIAG_NM",
                "病灶描述": "LSNS_DSCPT",  # 添加病灶描述字段
                "手术经过": "OPRT_PRCS_DSCPT",
                "术中情况": "OPRT_STTS_DSCPT",  # 添加术中情况字段
                "术中出血": "HMHG_VLU",
                "费用相关": "",
                "手术方式": "OPRT_WAY_DSCPT",  # 添加手术方式
                "麻醉方式": "ATHS_WAY_NM",  # 添加麻醉方式
                "手术医生": "OPRT_DOC_NM",  # 添加手术医生
                "麻醉医生": "ATHS_DOC_NM",  # 添加麻醉医生
                "手术部位": "OPRT_PRT_NM",  # 添加手术部位
                "切口愈合": "INCN_HEAL_STTS_NM"  # 添加切口愈合状态
            },
            "化疗记录": {
                "化疗药品名称": "化疗药品名称",
                "药品剂量": "药品剂量",
                "化疗方案": "化疗方案",
                "化疗周期": "化疗周期",
                "化疗日期": "化疗日期",
                "化疗反应": "化疗反应",
                "化疗效果": "化疗效果",
                "备注": "备注"
            }
        }

        # 护理记录映射 - 嵌套结构
        self.nursing_mapping = {
            "护理记录名": "出院小结(死亡小结)",
            "时间": "",
            "内容": {
                "基本信息": {
                    "出院诊断": "CDT_TNOVR_NM", "床号": "BED_NO", "科别": "ADMN_DPT_NM",
                    "入院时间": "ADMN_DT_TM", "出院时间": "DSCG_DT_TM", "姓名": "NM",
                    "性别": "GDR_NM", "年龄": "AGE", "住院号": "INHOS_NO",
                    "入院诊断": "ADMN_DIAG_WTM_DIAG_NM",
                    "年龄单位": "AGE_UNT"
                },
                "入院时简要病史": "BRF_DSES_HST",
                "体检摘要": "",
                "生命体征": {
                    "T": "TPR", "P": "PLS_RATE", "R": "BRTH_FRQ", "BP高": "STLC_PRS", "BP低": "DTLC_PRS"
                },
                "住院期间医疗情况": "",
                "出院时情况": "DSCG_CDT",
                "病程与治疗情况": "DIAG_TRTMT_PRCS_DSCPT",
                "出院后用药建议": "DSCG_ODR",
                "病人信息": {
                    "姓名": "NM", "性别": "GDR_NM", "科室": "ADMN_DPT_NM", "床号": "BED_NO",
                    "住院号": "INHOS_NO", "住院流水号": "INHOS_NO", "年龄": "AGE", "出生年月": "",
                    "入院时间": "ADMN_DT_TM", "出院时间": "DSCG_DT_TM"
                }
            }
        }

        # 在院评估单
        self.assessment_mapping = {"文书名": "", "时间": "", "基础评估": "", "置管状态": ""}

        # 特殊处理配置
        self.fields_to_concat = {
            "病理": {"报告内容": ["EXAM_RPT_RSLT_MICSCPC", "EXAM_RPT_RSLT_MACSCPC"]},
            "手术记录": {"手术经过": ["OPRT_PRCS_DSCPT", "OPRT_WAY_DSCPT"]},
            "医嘱": {"医嘱时间": ["ODR_STRT_DT", "ODR_END_DT"]},
            "护理记录": {
                "入院诊断": ["ADMN_DIAG_WTM_DIAG_NM", "ADMN_DIAG_TCM_DSES_NM"],
                "住院期间医疗情况": ["MAIN_TEST_RSLT", "LBRTR_EXAM_MAIN_CSTT", "ESPCL_EXAM", "PSTV_AXLR_EXAM_RSLT",
                                     "OTHR_MDC_DSPST"]
            }
        }

        # 带单位的字段
        self.fields_with_units = {
            "手术记录": {
                "费用相关": {
                    "fields": ["TRTMT_TP_OPRT_TRTMT_FEE", "TRTMT_TP_OPRT_FEE_ATHS_FEE", "TRTMT_TP_OPRT_FEE_OPRT_FEE"],
                    "units": ["元", "元", "元"],
                    "prefixes": ["治疗类-手术治疗费", "治疗类-手术治疗费-麻醉费", "治疗类-手术治疗费-手术费"]
                },
                "术中出血": {"field": "HMHG_VLU", "unit": "ml"}
            },
            "检验": {
                "检验结果": {"field": "TEST_RSLT_VLU", "unit_field": "TEST_RSLT_VLU_UNT"},
                "检验详情": {"field": "TEST_RSLT_VLU", "unit_field": "TEST_RSLT_VLU_UNT"}
            },
            "护理记录": {
                "体检摘要": {"fields": ["HGT", "WGT"], "units": ["cm", "kg"]}
            },
            "医嘱": {
                "单次剂量数量": {"field": "DRG_USE_ONCE_DOSG", "unit_field": "DRG_USE_ONCE_DOSG_UNT"},
                "单次给药数量": {"field": "DRG_USE_TOT_DOSG", "unit_field": "DRG_USE_TOT_DOSG_UNT"}
            }
        }
    # 工具方法
    def format_value(self, value):
        """格式化值，处理各种异常情况"""
        try:
            if value is None or value == "NULL" or value == "" or str(value).strip() == "":
                return "xxx"
            
            # 处理数字类型
            if isinstance(value, (int, float)):
                return str(value)
            
            # 处理字符串类型
            if isinstance(value, str):
                # 去除前后空格
                cleaned_value = value.strip()
                if cleaned_value == "" or cleaned_value.upper() == "NULL":
                    return "xxx"
                return cleaned_value
            
            # 其他类型转换为字符串
            return str(value)
        except Exception as e:
            print(f"警告: format_value处理异常 - 值: {value}, 错误: {e}")
            return "xxx"

    def format_date(self, date_str):
        """格式化日期，增强错误处理"""
        try:
            if not date_str or date_str == "NULL" or date_str == "" or str(date_str).strip() == "":
                return "xxx"
            
            # 如果已经是datetime对象
            if isinstance(date_str, datetime):
                return date_str.strftime("%Y-%m-%d %H:%M:%S")
            
            # 转换为字符串并清理
            date_str = str(date_str).strip()
            if date_str.upper() == "NULL" or date_str == "":
                return "xxx"
            
            # 尝试多种日期格式
            date_formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f",  # 包含微秒
                "%Y-%m-%d",
                "%Y%m%d%H%M%S",
                "%Y%m%d",
                "%Y/%m/%d %H:%M:%S",
                "%Y/%m/%d"
            ]
            
            for fmt in date_formats:
                try:
                    parsed_date = datetime.strptime(date_str, fmt)
                    return parsed_date.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    continue
            
            # 如果所有格式都失败，返回原始字符串（可能是有效的日期格式但不在我们的列表中）
            print(f"警告: 无法解析日期格式 - {date_str}")
            return date_str
            
        except Exception as e:
            print(f"警告: format_date处理异常 - 日期: {date_str}, 错误: {e}")
            return "xxx"

    def concat_fields(self, data, fields, separator="；"):
        """拼接多个字段，增强错误处理"""
        try:
            if not fields or not isinstance(fields, (list, tuple)):
                return "xxx"
            
            values = []
            for field in fields:
                if not field:  # 跳过空字段名
                    continue
                    
                value = data.get(field, "")
                if value and str(value).strip() != "" and str(value).upper() != "NULL":
                    cleaned_value = str(value).strip()
                    if cleaned_value:  # 确保清理后的值不为空
                        values.append(cleaned_value)
            
            return separator.join(values) if values else "xxx"
        except Exception as e:
            print(f"警告: concat_fields处理异常 - 字段: {fields}, 错误: {e}")
            return "xxx"

    def concat_fields_with_units(self, data, fields, units, separator="；", prefixes=None):
        """拼接带单位的字段，增强错误处理"""
        try:
            if not fields or not units or len(fields) != len(units):
                print(f"警告: 字段和单位数量不匹配 - 字段: {len(fields) if fields else 0}, 单位: {len(units) if units else 0}")
                return "xxx"
            
            values = []
            for i, (field, unit) in enumerate(zip(fields, units)):
                if not field:  # 跳过空字段名
                    continue
                    
                value = data.get(field, "")
                if value and str(value).strip() != "" and str(value).upper() != "NULL":
                    cleaned_value = str(value).strip()
                    if cleaned_value:  # 确保清理后的值不为空
                        prefix = ""
                        if prefixes and i < len(prefixes) and prefixes[i]:
                            prefix = f"{prefixes[i]}"
                        
                        unit_str = unit if unit else ""
                        values.append(f"{prefix}{cleaned_value}{unit_str}")
            
            return separator.join(values) if values else "xxx"
        except Exception as e:
            print(f"警告: concat_fields_with_units处理异常 - 字段: {fields}, 错误: {e}")
            return "xxx"

    # 嵌套映射处理
    def get_nested_value(self, data, mapping):
        result = {}
        for target_key, source_key in mapping.items():
            if isinstance(source_key, dict):
                result[target_key] = self.get_nested_value(data, source_key)
            else:
                if not source_key or source_key not in data or data.get(source_key) is None:
                    result[target_key] = "xxx"
                    continue
                value = data.get(source_key, "")
                if source_key.endswith("DT") or source_key.endswith(
                        "DT_TM") or "时间" in target_key or "日期" in target_key:
                    result[target_key] = self.format_date(value)
                else:
                    result[target_key] = self.format_value(value)
        return result

    # 特殊字段处理
    def apply_special_fields(self, data, module, record):
        # 字段拼接
        if module in self.fields_to_concat:
            for target, fields in self.fields_to_concat[module].items():
                if target in record:  # 只处理存在的字段
                    record[target] = self.concat_fields(data, fields)
        # 带单位的字段
        if module in self.fields_with_units:
            for target, config in self.fields_with_units[module].items():
                if "fields" in config and "units" in config:
                    prefixes = config.get("prefixes", None)
                    record[target] = self.concat_fields_with_units(
                        data, config["fields"], config["units"], prefixes=prefixes
                    )
                elif "field" in config and "unit" in config:
                    value = data.get(config["field"], "")
                    if value and value != "NULL" and value != "":
                        record[target] = f"{value}{config['unit']}"
                elif "field" in config and "unit_field" in config:
                    value = data.get(config["field"], "")
                    unit = data.get(config["unit_field"], "")
                    if value and value != "NULL" and value != "" and unit and unit != "NULL" and unit != "":
                        record[target] = f"{value}{unit}"
        return record

    # 模块处理方法
    def process_result(self, module, data_rows):
        if not data_rows: return []

        # 护理记录特殊处理
        if module == "护理记录": return self.process_nursing_records(data_rows)
        # 医嘱特殊处理
        if module == "医嘱": return self.process_medical_orders(data_rows)
        # 在院评估单特殊处理
        if module == "在院评估单": return self.process_assessment_form(data_rows)
        # 手术记录特殊处理
        if module == "手术记录": return self.process_surgery_records(data_rows)
        # 用药信息特殊处理
        if module == "用药信息": return self.process_medication_info(data_rows)

        # 通用处理
        results = []
        for row in data_rows:
            record = {}
            for target, source in self.module_mappings.get(module, {}).items():
                if source:
                    # 特殊处理检验模块中的TEST_ITM_NM
                    if module == "检验" and source == "TEST_ITM_NM":
                        record[target] = self.format_value(row.get("RSLT_TEST_ITM_NM", ""))
                    # 特殊处理带前缀的INHOS_NO
                    elif source == "INHOS_NO" and "RCD_INHOS_NO" in row:
                        record[target] = self.format_value(row.get("RCD_INHOS_NO", ""))
                    elif "时间" in target or "日期" in target:
                        record[target] = self.format_date(row.get(source))
                    else:
                        record[target] = self.format_value(row.get(source))
                else:
                    record[target] = "xxx"

            # 检验模块特殊处理：添加检验结果字段（由检测值和单位组合）
            if module == "检验":
                # 添加检验结果字段，初始值为xxx，后续在apply_special_fields中处理
                record["检验结果"] = "xxx"

            # 应用特殊字段处理
            record = self.apply_special_fields(row, module, record)
            results.append(record)
        return results
    # 护理记录处理
    # 在MedicalRecordConverter类中
    def process_nursing_records(self, data_rows, vital_signs=None):
        if not data_rows: return []
        results = [{"护理记录名": "xxx", "时间": "xxx", "内容": "xxx"}]  
        # 使用传入的生命体征或默认值
        default_vital_signs = {"T": "xxx", "P": "xxx", "R": "xxx", "BP高": "xxx", "BP低": "xxx"}
        vital_signs = vital_signs or default_vital_signs

        for row in data_rows:
            record = {
                "护理记录名": "出院小结(死亡小结)",
                "时间": "xxx",
                "内容": self.get_nested_value(row, self.nursing_mapping["内容"])
            }
            if "生命体征" in record["内容"]:
                record["内容"]["生命体征"] = vital_signs

            # 特殊字段处理 - 确保即使某些字段不存在也能正常处理
            if "基本信息" in record["内容"]:
                # 处理入院诊断
                admn_diag_wtm = row.get("ADMN_DIAG_WTM_DIAG_NM", "")
                admn_diag_tcm = row.get("ADMN_DIAG_TCM_DSES_NM", "")

                values = []
                if admn_diag_wtm and admn_diag_wtm != "NULL": values.append(str(admn_diag_wtm))
                if admn_diag_tcm and admn_diag_tcm != "NULL": values.append(str(admn_diag_tcm))

                record["内容"]["基本信息"]["入院诊断"] = "；".join(values) if values else "xxx"

            # 体检摘要处理
            hgt = row.get("HGT", "")
            wgt = row.get("WGT", "")

            values = []
            if hgt and hgt != "NULL": values.append(f"{hgt}cm")
            if wgt and wgt != "NULL": values.append(f"{wgt}kg")

            record["内容"]["体检摘要"] = "；".join(values) if values else "xxx"

            # 住院期间医疗情况处理
            medical_fields = ["MAIN_TEST_RSLT", "LBRTR_EXAM_MAIN_CSTT", "ESPCL_EXAM",
                              "PSTV_AXLR_EXAM_RSLT", "OTHR_MDC_DSPST"]

            values = []
            for field in medical_fields:
                value = row.get(field, "")
                if value and value != "NULL": values.append(str(value))

            record["内容"]["住院期间医疗情况"] = "；".join(values) if values else "xxx"

            results.append(record)
        return results

    # 医嘱处理
    def process_medical_orders(self, data_rows):
        if not data_rows: return []
        # 按医嘱ID分组
        orders_by_id = {}
        for row in data_rows:
            order_id = row.get("ODR_NO", "")
            if not order_id or order_id == "NULL": continue
            if order_id not in orders_by_id: orders_by_id[order_id] = []
            orders_by_id[order_id].append(row)
        # 构建医嘱记录
        results = []
        for order_id, rows in orders_by_id.items():
            order_details = []
            for row in rows:
                detail = {}
                for target, source in self.module_mappings["医嘱"].items():
                    if target not in ["医嘱id", "医嘱时间"] and source:
                        if "时间" in target:
                            detail[target] = self.format_date(row.get(source))
                        else:
                            detail[target] = self.format_value(row.get(source))
                    elif target not in ["医嘱id", "医嘱时间"]:
                        detail[target] = "xxx"

                # 特殊字段处理
                if row.get("DRG_USE_ONCE_DOSG") and row.get("DRG_USE_ONCE_DOSG_UNT"):
                    detail["单次剂量数量"] = f"{row.get('DRG_USE_ONCE_DOSG')}{row.get('DRG_USE_ONCE_DOSG_UNT')}"
                if row.get("DRG_USE_TOT_DOSG") and row.get("DRG_USE_TOT_DOSG_UNT"):
                    detail["单次给药数量"] = f"{row.get('DRG_USE_TOT_DOSG')}{row.get('DRG_USE_TOT_DOSG_UNT')}"

                order_details.append(detail)

            # 处理医嘱时间
            start_date = self.format_date(rows[0].get("ODR_STRT_DT") or rows[0].get("ODR_OPN_DT_TM"))
            end_date = self.format_date(rows[0].get("ODR_END_DT") or rows[0].get("ODR_STP_DT_TM"))
            medical_order_time = start_date
            if end_date != "xxx" and start_date != end_date:
                medical_order_time = f"{start_date} 至 {end_date}"

            # 创建医嘱记录
            for detail in order_details:  # 遍历医嘱详情中的每一项
                order_record = {
                    "医嘱id": order_id,
                    "申请时间": medical_order_time,
                    "医嘱项类别": detail.get("医嘱项类别", "xxx"),  # 从详情中提取字段
                    "项目名称": detail.get("项目名称", "xxx"),  # 从详情中提取字段
                    "医嘱项规格": detail.get("医嘱项规格", "xxx"),  # 从详情中提取字段
                    "单次剂量数量": detail.get("单次剂量数量", "xxx"),  # 从详情中提取字段
                    "给药途径": detail.get("给药途径", "xxx")  # 从详情中提取字段
                }
                results.append(order_record)
        return results

    # 在院评估单处理
    def process_assessment_form(self, data_rows):
        if not data_rows: return self.assessment_mapping

        # 使用第一条数据
        data = data_rows[0]
        result = {}

        for target, source in self.assessment_mapping.items():
            if source:
                if "时间" in target:
                    result[target] = self.format_date(data.get(source))
                else:
                    result[target] = self.format_value(data.get(source))
            else:
                result[target] = "xxx"
        return result

    # 手术记录处理
    def process_surgery_records(self, data_rows):
        if not data_rows: return []
        
        results = []
        for row in data_rows:
            record = {}
            
            # 基础字段映射
            for target, source in self.module_mappings.get("手术记录", {}).items():
                if source:
                    if "时间" in target or "日期" in target:
                        record[target] = self.format_date(row.get(source))
                    else:
                        record[target] = self.format_value(row.get(source))
                else:
                    record[target] = "xxx"
            
            # 应用特殊字段处理（字段拼接和带单位字段）
            record = self.apply_special_fields(row, "手术记录", record)
            
            # 手术记录特有的额外处理
            # 如果手术经过为空，尝试从其他相关字段获取信息
            if record.get("手术经过") == "xxx":
                alternative_fields = ["OPRT_DSCPT", "OPRT_DTLS", "OPRT_CNTNT"]
                for field in alternative_fields:
                    value = row.get(field, "")
                    if value and value != "NULL" and value != "":
                        record["手术经过"] = self.format_value(value)
                        break
            
            # 如果病灶描述为空，尝试从其他相关字段获取
            if record.get("病灶描述") == "xxx":
                alternative_fields = ["PTHLG_DSCPT", "LSNS_FNDG", "OPRT_FNDG"]
                for field in alternative_fields:
                    value = row.get(field, "")
                    if value and value != "NULL" and value != "":
                        record["病灶描述"] = self.format_value(value)
                        break
            
            # 如果术中情况为空，尝试从其他相关字段获取
            if record.get("术中情况") == "xxx":
                alternative_fields = ["OPRT_CNDTN", "INTR_OPRT_STTS", "OPRT_PRCS"]
                for field in alternative_fields:
                    value = row.get(field, "")
                    if value and value != "NULL" and value != "":
                        record["术中情况"] = self.format_value(value)
                        break
            
            results.append(record)
        return results

    def process_medication_info(self, data_rows):
        """
        处理用药信息三级JSON结构
        用药信息 -> 药品信息 -> 第n次开药
        """
        if not data_rows:
            return []
        
        # 按药品名分组，构建药品信息
        medication_groups = {}
        
        for row in data_rows:
            medication_name = self.format_value(row.get("CHRG_ITM_NM", ""))
            if medication_name == "xxx" or not medication_name:
                continue
            
            # 如果该药品名还未处理过，初始化药品信息
            if medication_name not in medication_groups:
                medication_groups[medication_name] = {
                    "药品名": medication_name,
                    "药品类别": self.format_value(row.get("FEE_CGY_NM", "")),
                    "药品通用名": self.format_value(row.get("DRG_CMN_NM", "")),
                    "药品国家编码": self.format_value(row.get("MDCR_DRG_CD_CTRY", "")),
                    "药品开具次数": "xxx",  # 稍后计算
                    "处方记录": []  # 存储该药品的所有开药记录
                }
            
            # 构建第n次开药记录
            prescription_record = {
                "药品收费时间": self.format_date(row.get("CHRG_DT")),
                "给药目的": self.format_value(row.get("DOS_PPS", "")),
                "药物使用总剂量": self.format_value(row.get("DRG_USE_TOT_DOSG", "")),
                "药品使用总剂量单位": self.format_value(row.get("DRG_USE_TOT_DOSG_UNT", "")),
                "药物使用次剂量": self.format_value(row.get("DRG_USE_ONCE_DOSG", "")),
                "药品使用次剂量单位": self.format_value(row.get("DRG_USE_ONCE_DOSG_UNT", "")),
                "药品使用频次名称": self.format_value(row.get("DRG_USE_FRQ_NM", ""))
            }
            
            # 将处方记录添加到对应药品
            medication_groups[medication_name]["处方记录"].append(prescription_record)
        
        # 构建最终的三级结构
        result = []
        for medication_name, medication_info in medication_groups.items():
            # 计算药品开具次数
            prescription_count = len(medication_info["处方记录"])
            medication_info["药品开具次数"] = str(prescription_count)
            
            # 构建第n次开药的结构
            medication_prescriptions = {}
            for i, prescription in enumerate(medication_info["处方记录"], 1):
                prescription_key = f"第{i}次开药"
                medication_prescriptions[prescription_key] = prescription
            
            # 构建药品信息结构（不包括处方记录，用第n次开药替代）
            drug_info = {
                "药品名": medication_info["药品名"],
                "药品类别": medication_info["药品类别"],
                "药品通用名": medication_info["药品通用名"],
                "药品国家编码": medication_info["药品国家编码"],
                "药品开具次数": medication_info["药品开具次数"],
                **medication_prescriptions  # 展开第n次开药
            }
            
            result.append(drug_info)
        
        # 按药品名排序
        result.sort(key=lambda x: x.get("药品名", ""))
        
        return result


# 大模型API调用
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

class MultiModelAPI:
    def __init__(self):
        # 定义三个模型的配置，SYvqwen最快，其他两个较慢
        self.models = [
            {
                "name": "Qwen2.5-7B-Instruct", 
                "url": "http://localhost:16666/v1/chat/completions",  # SYvqwen.py - 最快的模型
                "speed": "fast",
                "priority": 1
            },
            {
                "name": "SHC-7B", 
                "url": "http://localhost:54321/v1/chat/completions",  # SYfshc7b.py - 中等速度
                "speed": "medium",
                "priority": 2
            },
            {
                "name": "Qwen2.5-7B-Instruct", 
                "url": "http://localhost:54321/v1/chat/completions",  # SYfqwen.py - 第三个模型(你指出的配置)
                "speed": "medium",
                "priority": 3
            }
        ]
        
        # 为不同模块分配模型（让最快的模型处理最耗时的AI分析任务）
        self.module_assignments = {
            # 最快模型处理最耗时、最复杂的文档分析任务
            "入院记录": 0,        # Qwen2.5-7B (最快) - 最复杂的文档
            "出院记录": 0,        # Qwen2.5-7B (最快) - 总结性文档
            
            # 中等速度模型处理相对简单的文档分析任务
            "日常病程记录": 1,           # SHC-7B
            "上级医生查房记录": 1,       # SHC-7B
            "化疗记录": 1,               # SHC-7B - 化疗记录处理
            
            # 第三个模型处理剩余文档
            "首次病程记录": 2,           # 第三个Qwen模型
            "手术记录": 2,               # 第三个Qwen模型
            
            # 注意：检验、检查、医嘱、诊断、收费、医保、治疗用药等模块
            # 不需要AI处理，只做数据库查询和字段映射，所以不在这里分配
        }
        
        self.lock = threading.Lock()
        
    def send_chat_completion_request(self, model_config, message_content, temperature=0.01):
        """发送请求到指定模型"""
        url = model_config["url"]
        headers = {"Content-Type": "application/json"}
        data = {
            "model": model_config["name"],
            "messages": [{"role": "system",
                          "content": 'You are a helpful assistant. Follow the user\'s instruction carefully. 你需要直接返回JSON格式数据，不要添加任何额外的文字说明。'},
                         {"role": "user", "content": message_content}],
            "temperature": temperature,
            "max_tokens": 5000,
        }
        
        json_data = json.dumps(data)
        
        try:
            response = requests.post(url, headers=headers, data=json_data)
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                raise Exception(f"Request failed with status {response.status_code}: {response.text}")
        except Exception as e:
            return f"An error occurred: {type(e).__name__} - {e}"
    
    def get_model_for_module(self, module_name):
        """根据模块名称获取分配的模型"""
        model_index = self.module_assignments.get(module_name, 1)  # 默认使用中等速度模型
        return self.models[model_index]
    
    def process_module_parallel(self, module_tasks):
        """并行处理多个模块任务"""
        results = {}
        
        # 使用线程池并行处理
        with ThreadPoolExecutor(max_workers=3) as executor:
            # 提交所有任务
            future_to_module = {}
            for module_name, prompt in module_tasks.items():
                model_config = self.get_model_for_module(module_name)
                print(f"分配模块 '{module_name}' 给模型 '{model_config['name']}'")
                
                future = executor.submit(
                    self.send_chat_completion_request, 
                    model_config, 
                    prompt
                )
                future_to_module[future] = module_name
            
            # 收集结果
            for future in as_completed(future_to_module):
                module_name = future_to_module[future]
                try:
                    result = future.result()
                    results[module_name] = result
                    print(f"模块 '{module_name}' 处理完成")
                except Exception as e:
                    print(f"模块 '{module_name}' 处理失败: {e}")
                    results[module_name] = f"处理失败: {e}"
        
        return results
    
    def chat_method_for_module(self, module_name, content):
        """为特定模块处理内容"""
        model_config = self.get_model_for_module(module_name)
        return self.send_chat_completion_request(model_config, content)
    
    def process_documents_parallel(self, document_tasks):
        """并行处理多个文档任务
        
        Args:
            document_tasks: dict, 格式为 {文档类型: (原始数据, 处理函数)}
        
        Returns:
            dict: 处理后的结果，格式为 {文档类型: 提取结果}
        """
        print(f"开始并行处理 {len(document_tasks)} 个文档...")
        results = {}
        
        # 使用线程池并行处理
        with ThreadPoolExecutor(max_workers=3) as executor:
            # 提交所有任务
            future_to_doc = {}
            for doc_type, (raw_data, process_func) in document_tasks.items():
                if raw_data:  # 只处理有数据的文档
                    print(f"提交文档 '{doc_type}' 到并行处理队列")
                    future = executor.submit(process_func, raw_data)
                    future_to_doc[future] = doc_type
                else:
                    # 如果没有原始数据，直接设置为空结果
                    results[doc_type] = {}
                    print(f"文档 '{doc_type}' 无数据，跳过处理")
            
            # 收集结果
            for future in as_completed(future_to_doc):
                doc_type = future_to_doc[future]
                try:
                    result = future.result()
                    results[doc_type] = result
                    print(f"文档 '{doc_type}' 处理完成")
                except Exception as e:
                    print(f"文档 '{doc_type}' 处理失败: {e}")
                    results[doc_type] = {}
        
        print("所有文档并行处理完成")
        return results

# 创建全局多模型API实例
multi_model_api = MultiModelAPI()

# 保持原有的单模型接口向后兼容
def send_chat_completion_request(model_name, message_content, temperature=0.01):
    # 使用最快的模型作为默认模型
    model_config = {
        "name": model_name,
        "url": "http://localhost:16666/v1/chat/completions"  # 使用最快的模型
    }
    return multi_model_api.send_chat_completion_request(model_config, message_content, temperature)

def chat_method(content):
    return send_chat_completion_request("Qwen2.5-7B-Instruct", content)  # 使用最快的模型


class MedicalDataProcessor:
    def extract_discharge_diagnosis_first_item(self, discharge_content):
        """直接从出院记录文本中提取出院诊断的第一条，不使用大模型"""
        if not discharge_content:
            print("警告: 出院记录内容为空")
            return "文本中未提及该内容"

        import re

        print("\n开始直接提取出院诊断...")
        print("-" * 60)
        print(f"出院记录内容预览: {discharge_content[:100]}...")

        # 方法1：精确匹配"出院诊断："后的第一个"1."条目，直到下一个编号或行尾
        pattern1 = r'出院诊断[：:]\s*(?:\n|\r\n)?\s*1[\.\、]([^。\n\r\d;；]+?)(?=\s*\d+[\.\、]|\n|$)'
        match = re.search(pattern1, discharge_content, re.DOTALL)
        if match:
            result = match.group(1).strip()
            print(f"方法1找到第一个诊断: {result}")
            return result

        # 方法2：找到包含"出院诊断"的段落，然后提取该段落中的第一个"1."项
        diagnosis_section_pattern = r'出院诊断[：:].*?(?=入院诊断|诊疗经过|出院情况|\n\n|\Z)'
        diagnosis_section = re.search(diagnosis_section_pattern, discharge_content, re.DOTALL)

        if diagnosis_section:
            section_text = diagnosis_section.group(0)
            # 在该段落中查找第一个"1."项
            first_item = re.search(r'1[\.\、]([^。\n\r\d;；]+?)(?=\s*\d+[\.\、]|\n|$)', section_text)
            if first_item:
                result = first_item.group(1).strip()
                print(f"方法2找到段落中的第一个诊断: {result}")
                return result

        # 方法3：按行处理，找到"出院诊断"行后的第一个"1."开头的行
        lines = discharge_content.split('\n')
        found_diagnosis_header = False

        for line in lines:
            if '出院诊断' in line:
                found_diagnosis_header = True
                # 检查当前行是否已包含"1."
                item_in_line = re.search(r'出院诊断[：:].*?1[\.\、]([^。\n\r\d;；]+)', line)
                if item_in_line:
                    result = item_in_line.group(1).strip()
                    print(f"方法3找到同行的第一个诊断: {result}")
                    return result
                continue

            if found_diagnosis_header:
                # 查找"1."开头的行
                item_match = re.search(r'^\s*1[\.\、]([^。\n\r\d;；]+)', line)
                if item_match:
                    result = item_match.group(1).strip()
                    print(f"方法3找到后续行的第一个诊断: {result}")
                    return result

        print("警告: 未能匹配任何出院诊断模式")
        return "文本中未提及该内容"

    def is_icd10_in_range(self, icd10_code, range_expression):
        """
        全面检查ICD10编码是否在指定范围内 - 增强版
        """
        # 如果输入无效，直接返回False
        if not icd10_code or icd10_code == "未找到匹配ICD10编码":
            return False, None

        # 记录详细日志
        print(f"检查编码 {icd10_code} 是否在范围 {range_expression} 内")

        # 预处理范围表达式，移除可能的BOM标记和其他非打印字符
        range_expression = range_expression.replace('\ufeff', '').strip()

        # 优化分割范围表达式的方法
        range_parts = []
        # 处理多种可能的分隔符组合
        for part in re.split(r'[,，、]或|或(?!\w)|、|,|;|；', range_expression):
            part = part.strip()
            if part:
                range_parts.append(part)

        print(f"解析后的范围表达式: {range_parts}")

        # 遍历所有范围表达式部分
        for range_part in range_parts:
            try:
                # 1. 范围表达式匹配（如"G20至G30"或"G20-G30"）
                if '至' in range_part or '-' in range_part:
                    separator = '至' if '至' in range_part else '-'
                    start, end = range_part.split(separator)
                    start, end = start.strip(), end.strip()

                    # 直接匹配处理
                    if icd10_code == start or icd10_code == end:
                        return True, range_part

                    # 获取前缀和数字部分
                    start_match = re.match(r'([A-Z]+)(\d+)(.*)', start)
                    end_match = re.match(r'([A-Z]+)(\d+)(.*)', end)
                    code_match = re.match(r'([A-Z]+)(\d+)(.*)', icd10_code)

                    # 如果任何一个不符合格式，跳过
                    if not (start_match and end_match and code_match):
                        continue

                    # 提取前缀和数字部分
                    start_prefix, start_num, start_suffix = start_match.groups()
                    end_prefix, end_num, end_suffix = end_match.groups()
                    code_prefix, code_num, code_suffix = code_match.groups()

                    # 前缀必须匹配
                    if code_prefix != start_prefix or code_prefix != end_prefix:
                        continue

                    # 比较主要数字部分
                    if int(start_num) <= int(code_num) <= int(end_num):
                        # 如果不涉及小数部分，则在范围内
                        if not (start_suffix or end_suffix or code_suffix):
                            return True, range_part

                        # 如果编码有小数部分但范围边界没有，则在范围内
                        if code_suffix and not start_suffix and not end_suffix:
                            return True, range_part

                        # 处理小数部分比较（简化逻辑）
                        if start_suffix and end_suffix and code_suffix:
                            if code_num == start_num and code_suffix < start_suffix:
                                continue
                            if code_num == end_num and code_suffix > end_suffix:
                                continue
                            return True, range_part

                # 2. 通配符匹配
                elif 'x' in range_part.lower() or 'X' in range_part or '*' in range_part:
                    # 构建正则表达式
                    pattern = range_part.replace('*', '.*')
                    pattern = pattern.replace('x', '\\d').replace('X', '\\d')
                    pattern = f"^{pattern}$"

                    # 直接用正则匹配
                    if re.match(pattern, icd10_code):
                        return True, range_part

                    # 特殊处理：前缀+通配符匹配
                    if '.' in range_part and '.' in icd10_code:
                        code_parts = icd10_code.split('.', 1)
                        pattern_parts = range_part.split('.', 1)

                        # 如果主编码部分匹配且模式是通配符
                        if code_parts[0] == pattern_parts[0] and (
                                'x' in pattern_parts[1].lower() or '*' in pattern_parts[1]):
                            return True, range_part

                # 3. "+"结尾表示所有子编码
                elif range_part.endswith('+'):
                    base_code = range_part[:-1].strip()
                    if icd10_code.startswith(base_code):
                        return True, range_part

                # 4. 精确匹配和父子关系检查
                else:
                    # 精确匹配
                    if icd10_code == range_part:
                        return True, range_part

                    # 改进：更好地处理父子关系，特别是G41.9和G41.900这种情况

                    # 情况1: 如果范围中没有小数点，检查是否编码属于该分类
                    if '.' not in range_part:
                        # 不带小数点的编码前缀匹配 (如"G41")
                        code_prefix_match = re.match(r'([A-Z]+\d+)', icd10_code)
                        if code_prefix_match and code_prefix_match.group(1) == range_part:
                            return True, range_part

                    # 情况2: 检查编码是否以范围部分开头（考虑小数点）
                    if '.' in icd10_code:
                        # 分割编码和范围以进行比较
                        code_parts = icd10_code.split('.')
                        code_base = code_parts[0]

                        # 如果基础部分匹配，直接返回匹配
                        if code_base == range_part:
                            return True, range_part

                    # 子编码匹配（如G20.1是G20的子编码）
                    if '.' not in range_part and icd10_code.startswith(range_part + '.'):
                        return True, range_part

                    # 父编码匹配（范围中有G20.1，编码是G20.123）
                    if '.' in range_part and icd10_code.startswith(range_part):
                        # 直接检查是否是前缀匹配，不再要求后缀必须以点号开头
                        return True, range_part

            except Exception as e:
                print(f"处理范围 {range_part} 时出错: {e}")
                # 继续处理下一个范围表达式

        print(f"编码 {icd10_code} 不在范围 {range_expression} 内")
        return False, None
    def _is_in_simple_range(self, code, start, end):
        """检查不带小数点的编码是否在范围内"""
        # 提取前缀和数字部分
        code_prefix = ''.join(c for c in code if c.isalpha())
        code_num = int(''.join(c for c in code if c.isdigit()))

        start_prefix = ''.join(c for c in start if c.isalpha())
        start_num = int(''.join(c for c in start if c.isdigit()))

        end_prefix = ''.join(c for c in end if c.isalpha())
        end_num = int(''.join(c for c in end if c.isdigit()))

        # 前缀必须匹配
        if code_prefix != start_prefix or code_prefix != end_prefix:
            return False

        # 检查数字部分是否在范围内
        return start_num <= code_num <= end_num

    def _is_in_decimal_range(self, code, start, end):
        """检查带小数点的编码是否在范围内"""
        import re

        # 提取主编码部分（如G20）
        code_main = re.match(r'([A-Z]\d+)', code)
        start_main = re.match(r'([A-Z]\d+)', start)
        end_main = re.match(r'([A-Z]\d+)', end)

        if not (code_main and start_main and end_main):
            return False

        # 主编码部分必须匹配
        if not (code_main.group(1) == start_main.group(1) == end_main.group(1)):
            return False

        # 提取小数部分
        code_decimal = code[len(code_main.group(0)):] if '.' in code else ""
        start_decimal = start[len(start_main.group(0)):] if '.' in start else ""
        end_decimal = end[len(end_main.group(0)):] if '.' in end else ""

        # 处理小数部分为空的情况
        if not code_decimal and (start_decimal or end_decimal):
            return False

        # 小数部分比较
        if code_decimal and start_decimal and end_decimal:
            try:
                code_num = float("0" + code_decimal)
                start_num = float("0" + start_decimal)
                end_num = float("0" + end_decimal)
                return start_num <= code_num <= end_num
            except ValueError:
                # 如果无法转换为数字，按字符串比较
                return start_decimal <= code_decimal <= end_decimal

        return True

    def extract_main_icd10_code(self, discharge_diag, diagnosis_list):
        """两阶段ICD10匹配：先规则匹配，失败后大模型匹配"""
        # 检查输入
        if not discharge_diag or discharge_diag == "文本中未提及该内容":
            print("警告: 未找到有效的出院诊断")
            return {"code": "未找到匹配ICD10编码", "name": "未找到出院诊断", "match_rate": 0}

        if not diagnosis_list:
            print("警告: 未找到任何诊断记录")
            return {"code": "未找到ICD10编码", "name": "未找到诊断记录", "match_rate": 0}

        # 检查是否有有效的ICD10编码
        valid_icd_codes = [diag for diag in diagnosis_list if
                           diag.get("ICD10编码", "xxx") != "xxx" and
                           diag.get("ICD10名称", "xxx") != "xxx"]

        if not valid_icd_codes:
            print("警告: 未找到有效的ICD10编码")
            return {"code": "未找到有效ICD10编码", "name": "未找到有效ICD10名称", "match_rate": 0}

        # 提取出院诊断的第一条内容
        first_discharge_diag = discharge_diag.split("；")[0].split("\n")[0].strip()
        print(f"提取的出院诊断第一条内容: {first_discharge_diag}")

        if not first_discharge_diag:
            print("警告: 未能提取出院诊断第一条内容")
            return {"code": "未找到匹配ICD10编码", "name": "未能提取出院诊断内容", "match_rate": 0}

        # 第一阶段：使用规则匹配
        try:
            print("第一阶段：执行规则匹配...")
            rule_based_result = self._rule_based_icd10_match(first_discharge_diag, valid_icd_codes)

            # 设置规则匹配的阈值，决定是否需要大模型匹配
            RULE_MATCH_THRESHOLD = 70  # 如果规则匹配度超过70%，认为是可靠匹配

            if rule_based_result and rule_based_result.get("match_rate", 0) >= RULE_MATCH_THRESHOLD:
                print(f"规则匹配成功! 匹配度: {rule_based_result.get('match_rate')}%")
                return rule_based_result

            # 第二阶段：如果规则匹配不理想，使用大模型匹配
            print("规则匹配度不够理想，进入第二阶段：大模型匹配...")
            llm_result = self._llm_based_icd10_match(first_discharge_diag, valid_icd_codes)

            if llm_result:
                print(f"大模型匹配结果: {llm_result}")
                return llm_result
            else:
                # 如果大模型也没有返回有效结果，回退到规则匹配结果
                print("大模型匹配失败，回退到规则匹配结果")
                return rule_based_result if rule_based_result else {
                    "code": "未找到匹配ICD10编码",
                    "name": "未找到匹配ICD10名称",
                    "match_rate": 0
                }
        except Exception as e:
            print(f"匹配过程出错: {e}")
            import traceback
            traceback.print_exc()
            # 出错时返回默认结果
            return {"code": "未找到匹配ICD10编码", "name": "未找到匹配ICD10名称", "match_rate": 0}

    def _rule_based_icd10_match(self, diagnosis_text, icd10_codes):
        """增强版规则匹配"""
        print(f"\n对出院诊断 \"{diagnosis_text}\" 进行规则匹配")
        print("-" * 60)

        best_match = None
        highest_score = 0

        # 清理和标准化诊断文本
        def normalize_text(text):
            # 标准化空格和标点
            text = re.sub(r'[、，,；;]', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text

        normalized_diagnosis = normalize_text(diagnosis_text)

        # 医学术语等价词典
        medical_terms = {
            "发作期": ["加重期", "急性期", "恶化期"],
            "加重期": ["发作期", "急性期", "恶化期"],
            "慢阻肺": ["慢性阻塞性肺病", "慢性阻塞性肺疾病"],
            "支气管炎急性发作": ["支气管急性发作", "支气管炎急性加重"]
        }

        # 1. 完全精确匹配
        for code_info in icd10_codes:
            code = code_info.get("ICD10编码", "")
            name = code_info.get("ICD10名称", "")

            if normalized_diagnosis == normalize_text(name):
                print(f"精确匹配成功! {code} | {name} [匹配度=100%]")
                return {"code": code, "name": name, "match_rate": 100}

        # 2. 医学等价词匹配
        for code_info in icd10_codes:
            code = code_info.get("ICD10编码", "")
            name = code_info.get("ICD10名称", "")

            for term, synonyms in medical_terms.items():
                if term in diagnosis_text:
                    for synonym in synonyms:
                        if synonym in name:
                            test_diagnosis = diagnosis_text.replace(term, synonym)
                            if normalize_text(test_diagnosis) == normalize_text(name):
                                print(f"医学等价词匹配! {code} | {name} [匹配度=95%]")
                                return {"code": code, "name": name, "match_rate": 95}

        # 3. 分解评分匹配
        # 核心疾病词、修饰词和状态词
        core_diseases = ["肺炎", "支气管炎", "心力衰竭", "冠心病", "糖尿病", "高血压",
                         "肝炎", "肾病", "肾炎", "脑炎", "胃炎", "肠炎"]
        modifiers = ["急性", "慢性", "重症", "轻度", "中度", "重度", "复发性", "进行性", "阻塞性"]
        status_terms = ["加重", "发作", "恶化", "期", "阶段", "并发症", "伴有"]

        for code_info in icd10_codes:
            code = code_info.get("ICD10编码", "")
            name = code_info.get("ICD10名称", "")

            score = 0
            match_details = []

            # 核心疾病匹配
            for disease in core_diseases:
                if disease in diagnosis_text and disease in name:
                    disease_score = 50
                    score += disease_score
                    match_details.append(f"核心疾病'{disease}'匹配 (+{disease_score}分)")

            # 修饰词匹配
            for modifier in modifiers:
                if modifier in diagnosis_text and modifier in name:
                    modifier_score = 15
                    score += modifier_score
                    match_details.append(f"修饰词'{modifier}'匹配 (+{modifier_score}分)")

            # 状态词匹配
            for term in status_terms:
                if term in diagnosis_text and term in name:
                    term_score = 10
                    score += term_score
                    match_details.append(f"状态词'{term}'匹配 (+{term_score}分)")

            # 字符重叠分析
            diag_chars = set(diagnosis_text)
            name_chars = set(name)
            overlap = len(diag_chars.intersection(name_chars))
            overlap_ratio = overlap / len(name_chars) if name_chars else 0
            overlap_score = int(overlap_ratio * 25)

            score += overlap_score
            match_details.append(f"字符重叠率: {overlap}/{len(name_chars)}={overlap_ratio:.2f} (+{overlap_score}分)")

            # 连续短语匹配
            for phrase_length in range(3, 7):  # 检查3-6字的短语
                for i in range(len(diagnosis_text) - phrase_length + 1):
                    phrase = diagnosis_text[i:i + phrase_length]
                    if phrase in name and len(phrase) >= 3:
                        bonus = len(phrase) * 2
                        score += bonus
                        match_details.append(f"短语'{phrase}'匹配 (+{bonus}分)")
                        break

            # 记录详细的分数
            if score > 0:
                detail_str = "; ".join(match_details)
                print(f"{code} | {name} -> 得分: {score} - {detail_str}")

                if score > highest_score:
                    highest_score = score
                    best_match = {"code": code, "name": name, "match_rate": min(score, 100)}

        # 返回最佳匹配结果
        if best_match:
            print(
                f"\n规则匹配最佳结果: {best_match['code']} | {best_match['name']} [匹配度={best_match['match_rate']}%]")
        else:
            print("规则匹配未找到任何匹配项")

        return best_match

    def _llm_based_icd10_match(self, diagnosis_text, icd10_codes):
        """使用大模型匹配ICD10编码"""
        print("\n使用大模型进行ICD10编码匹配...")

        # 为大模型构建有限的ICD10编码列表
        # 最多选择前20条编码避免提示词过长
        icd_list_str = ""
        for i, code_info in enumerate(icd10_codes[:50], 1):
            code = code_info.get("ICD10编码", "")
            name = code_info.get("ICD10名称", "")
            icd_list_str += f"{i}. 编码: {code} | 名称: {name}\n"

        # 构建提示词
        prompt = f"""
    作为医学编码专家，请从以下ICD10编码列表中，找出与给定出院诊断最匹配的一个编码。
    出院诊断: {diagnosis_text}
    可选的ICD10编码列表:
    {icd_list_str}
    请分析诊断文本与每个ICD10编码名称的相似度，考虑以下因素:
    1. 核心疾病是否匹配（如"肺炎"、"心力衰竭"等）
    2. 修饰词是否匹配（如"急性"、"慢性"、"重度"等）
    3. 疾病状态是否匹配（如"加重期"、"发作期"等）
    4. 医学上的同义表达（如"加重期"和"发作期"在医学上可视为等价）
    请仅返回一个JSON格式的结果，包含最匹配的编码、名称和匹配度评分(0-100)：
    {{
      "code": "最匹配的ICD10编码",
      "name": "最匹配的ICD10名称",
      "match_rate": 匹配度评分(0-100的整数),
      "reasoning": "简要解释为什么选择这个编码作为最佳匹配"
    }}
    如果无法找到合适的匹配，请返回：
    {{
      "code": "未找到匹配ICD10编码",
      "name": "未找到匹配ICD10名称",
      "match_rate": 0,
      "reasoning": "未找到匹配的原因"
    }}
        """

        try:
            # 调用大模型 (ICD10匹配使用默认模型)
            response = chat_method(prompt)
            print("大模型响应成功")

            # 解析JSON响应
            try:
                # 提取JSON部分
                json_start = response.find("{")
                json_end = response.rfind("}") + 1

                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    result = json.loads(json_str)

                    # 提取核心字段
                    match_result = {
                        "code": result.get("code", "未找到匹配ICD10编码"),
                        "name": result.get("name", "未找到匹配ICD10名称"),
                        "match_rate": result.get("match_rate", 0)
                    }

                    # 打印匹配原因（但不包含在返回结果中）
                    if "reasoning" in result:
                        print(f"匹配原因: {result['reasoning']}")

                    return match_result
                else:
                    print("大模型响应中未找到JSON结构")
                    return None
            except Exception as e:
                print(f"解析大模型响应出错: {e}")
                return None
        except Exception as e:
            print(f"调用大模型出错: {e}")
            return None
    def ensure_unique_columns(self, df):
        """确保DataFrame列名唯一，通过手动重命名重复列。"""
        if df.columns.duplicated().any():
            print("警告: DataFrame有重复列名，自动重命名...")

            # 创建一个新的列名列表
            new_columns = []
            seen = set()
            for col in df.columns:
                if col in seen:
                    # 如果列名已存在，添加数字后缀
                    count = 1
                    new_col = f"{col}_{count}"
                    while new_col in seen:
                        count += 1
                        new_col = f"{col}_{count}"
                    new_columns.append(new_col)
                    seen.add(new_col)
                else:
                    new_columns.append(col)
                    seen.add(col)
            df.columns = new_columns
        return df

    def __del__(self):
        """析构函数，确保关闭数据库连接"""
        if hasattr(self, 'connection') and self.connection:
            try:
                self.connection.close()
                print("数据库连接已关闭")
            except Exception as e:
                print(f"")

    def __init__(self, inhos_no=DEFAULT_INHOS_NO):
        self.inhos_no = inhos_no
        self.converter = MedicalRecordConverter()
        self.extracted_vital_signs = {"T": "xxx", "P": "xxx", "R": "xxx", "BP高": "xxx", "BP低": "xxx"}

        # 数据库连接代码
        self.connection = None
        try:
            # 使用pymysql直接连接
            self.connection = pymysql.connect(**DB_CONFIG)
            print(f"数据库连接已建立")
        except Exception as e:
            print(f"数据库连接失败: {e}")
            sys.exit(1)

        # 设置模块查询语句
        self.module_queries = {
            "病理": f"""
                SELECT rcd.INHOS_NO as RCD_INHOS_NO, rcd.PTHLG_EXAM_TP_NM, rcd.EXAM_DT, 
                    rpt.PTHLG_DIAG, rpt.EXAM_RPT_RSLT_MICSCPC, rpt.EXAM_RPT_RSLT_MACSCPC, 
                    rpt.IMNHSTCHMCL_DTCT_RSLT, rpt.EXAM_RSLT, rpt.RPT_DT,
                    rcd.PTHLG_RCD_NO as RCD_PTHLG_RCD_NO, rpt.PTHLG_RCD_NO as RPT_PTHLG_RCD_NO,
                    rcd.INVLD_FLG as RCD_INVLD_FLG, rpt.INVLD_FLG as RPT_INVLD_FLG,
                    GROUP_CONCAT(DISTINCT diag.DIAG_DSCPT SEPARATOR '，') as DIAG_DSCPT
                FROM FACT_PTHLG_RCD rcd 
                LEFT JOIN FACT_PTHLG_RPT rpt ON rcd.PTHLG_RCD_NO = rpt.PTHLG_RCD_NO
                LEFT JOIN FACT_INHOS_DIAG_INFMT diag ON rcd.INHOS_NO = diag.INHOS_NO AND diag.INVLD_FLG = 0
                WHERE rcd.INHOS_NO = '{self.inhos_no}'
                GROUP BY rcd.INHOS_NO, rcd.PTHLG_EXAM_TP_NM, rcd.EXAM_DT, 
                    rpt.PTHLG_DIAG, rpt.EXAM_RPT_RSLT_MICSCPC, rpt.EXAM_RPT_RSLT_MACSCPC, 
                    rpt.IMNHSTCHMCL_DTCT_RSLT, rpt.EXAM_RSLT, rpt.RPT_DT,
                    rcd.PTHLG_RCD_NO, rpt.PTHLG_RCD_NO,
                    rcd.INVLD_FLG, rpt.INVLD_FLG;
            """,
            "医嘱": f"""
                SELECT ODR_NO, ODR_STRT_DT, ODR_END_DT, ODR_SQNC_NO, INHOS_NO, ODR_ITM_TP_NM, 
                    ODR_ITM_TP_CD, ODR_EXEC_STRT_DT, ODR_EXEC_CPLT_DT, ODR_EXEC_STTS_NM, 
                    ODR_STP_DT_TM, ODR_ITM_CD, ODR_ITM_NM, DRG_SPCF, DRG_USE_ONCE_DOSG, 
                    DRG_USE_ONCE_DOSG_UNT, DRG_USE_TOT_DOSG, DRG_USE_TOT_DOSG_UNT, 
                    DOS_RUT_NM, DRG_USE_FRQ_NM, INVLD_FLG
                FROM FACT_INHOS_ODR_INFMT 
                WHERE INHOS_NO = '{self.inhos_no}';
            """,
            "护理记录": f"""
                SELECT DISTINCT 
                    m.ADMN_DPT_NM, m.ADMN_DT_TM, m.DSCG_DT_TM, m.NM as M_NM, m.GDR_NM as M_GDR_NM, m.AGE as M_AGE, m.AGE_UNT as M_AGE_UNT, m.INHOS_NO as M_INHOS_NO,
                    d.ADMN_DIAG_WTM_DIAG_NM, d.ADMN_DIAG_TCM_DSES_NM, d.CDT_TNOVR_NM, d.INHOS_NO as D_INHOS_NO,
                    t.BED_NO, t.INHOS_NO as T_INHOS_NO,
                    a.HGT, a.WGT, a.BRF_DSES_HST, a.TPR, a.PLS_RATE, a.BRTH_FRQ, a.STLC_PRS, a.DTLC_PRS, a.INHOS_NO as A_INHOS_NO,
                    dc.MAIN_TEST_RSLT, dc.LBRTR_EXAM_MAIN_CSTT, dc.ESPCL_EXAM, dc.PSTV_AXLR_EXAM_RSLT,
                    dc.OTHR_MDC_DSPST, dc.DSCG_CDT, dc.DIAG_TRTMT_PRCS_DSCPT, dc.DSCG_ODR, dc.INHOS_NO as DC_INHOS_NO,
                    m.INVLD_FLG as M_INVLD_FLG, d.INVLD_FLG as D_INVLD_FLG, 
                    t.INVLD_FLG as T_INVLD_FLG, a.INVLD_FLG as A_INVLD_FLG, 
                    dc.INVLD_FLG as DC_INVLD_FLG
                FROM FACT_MDC_RCD_HMPG m
                LEFT JOIN FACT_DSCG_RCD d ON m.INHOS_NO = d.INHOS_NO
                LEFT JOIN FACT_TCM_MDC_RCD_HMPG t ON m.INHOS_NO = t.INHOS_NO
                LEFT JOIN FACT_ADMN_MDC_HTR_RCD a ON m.INHOS_NO = a.INHOS_NO
                LEFT JOIN FACT_DSCG_MDC_HTR_RCD dc ON m.INHOS_NO = dc.INHOS_NO
                WHERE m.INHOS_NO = '{self.inhos_no}';
            """,
            "检查": f"""
                SELECT DISTINCT 
                    rcd.INHOS_NO as RCD_INHOS_NO, rcd.EXAM_RCD_NO as RCD_EXAM_RCD_NO, rcd.EXAM_ITM_TP_NM, rcd.EXAM_PRT_NM, rcd.EXAM_ITM_NM,
                    rcd.EXAM_PRCS_DSCPT, rcd.APL_DT_TM, rcd.EXAM_DT,
                    rpt.EXAM_RPT_RSLT_OBJCT, rpt.EXAM_RPT_RSLT_SBJCT, rpt.EXAM_RPT_DT,
                    rpt.EXAM_RCD_NO as RPT_EXAM_RCD_NO,
                    rcd.INVLD_FLG as RCD_INVLD_FLG, rpt.INVLD_FLG as RPT_INVLD_FLG
                FROM FACT_EXAM_RCD rcd
                LEFT JOIN FACT_EXAM_RPT rpt ON rcd.EXAM_RCD_NO = rpt.EXAM_RCD_NO
                WHERE rcd.INHOS_NO = '{self.inhos_no}';
            """,
            "检验": f"""
                SELECT DISTINCT 
                    rcd.INHOS_NO as RCD_INHOS_NO, rcd.TEST_RCD_NO, rcd.APL_DT_TM, rcd.TEST_DT, rcd.TEST_RPT_DT,
                    rcd.TEST_ITM_NM as RCD_TEST_ITM_NM, rcd.TEST_ITM_TP_NM, rslt.TEST_RSLT, rslt.TEST_RSLT_VLU,
                    rslt.TEST_RSLT_VLU_UNT, rslt.NML_VLU_MAX, rslt.NML_VLU_MIN, rslt.TEST_ITM_NM as RSLT_TEST_ITM_NM,
                    rslt.TEST_CHD_ITM_CD, rslt.TEST_CHD_ITM_NM,
                    rcd.TEST_RPT_NO as RCD_TEST_RPT_NO, rslt.TEST_RPT_NO as RSLT_TEST_RPT_NO,
                    rcd.INVLD_FLG as RCD_INVLD_FLG, rslt.INVLD_FLG as RSLT_INVLD_FLG
                FROM FACT_TEST_RCD rcd
                LEFT JOIN FACT_TEST_RPT_CVT_RSLT rslt
                ON rcd.TEST_RPT_NO = rslt.TEST_RPT_NO AND rcd.TEST_ITM_NM = rslt.TEST_ITM_NM
                WHERE rcd.INHOS_NO = '{self.inhos_no}';
            """,
            "诊断": f"""
                SELECT INHOS_NO, DIAG_ICD10_CD,DIAG_ICD10_NM, DIAG_RCD_NO, DIAG_DT, DIAG_DSCPT, DIAG_CGY_NM, DIAG_CD, INVLD_FLG
                FROM FACT_INHOS_DIAG_INFMT 
                WHERE INHOS_NO = '{self.inhos_no}';
            """,
            "诊断信息": f"""
                SELECT INHOS_NO, DIAG_NM, DIAG_CD, DIAG_SRL_NO, MAIN_DIAG_FLG
                FROM FACT_MDC_RCD_HMPG_DIAG 
                WHERE INHOS_NO = '{self.inhos_no}';
            """,
            "用药信息": f"""
                SELECT 
                    fee.CHRG_ITM_NM,
                    fee.FEE_CGY_NM,
                    fee.CHRG_DT,
                    fee.CHRG_ITM_CD,
                    fee.PRM_KEY,
                    fee.CHRG_RTRN_FLG,
                    drg.DRG_CMN_NM,
                    drg.MDCR_DRG_CD_CTRY,
                    fo.ORDER_NO,
                    odr.DOS_PPS,
                    odr.DRG_USE_TOT_DOSG,
                    odr.DRG_USE_TOT_DOSG_UNT,
                    odr.DRG_USE_ONCE_DOSG,
                    odr.DRG_USE_ONCE_DOSG_UNT,
                    odr.DRG_USE_FRQ_NM
                FROM FACT_INHOS_FEE_DTL fee
                LEFT JOIN DIM_DRG_INFMT drg ON fee.CHRG_ITM_CD = drg.DRG_CD
                LEFT JOIN FACT_FEEDTL_ORDER fo ON fee.PRM_KEY = fo.PRM_KEY
                LEFT JOIN FACT_INHOS_ODR_INFMT odr ON fo.ORDER_NO = odr.ODR_NO
                WHERE fee.INHOS_NO = '{self.inhos_no}'
                    AND fee.FEE_CGY_NM IN ('中成药', '中草药', '西药')
                    AND fee.CHRG_RTRN_FLG = 1
                    AND fee.INVLD_FLG = 0
                    AND (odr.INVLD_FLG = 0 OR odr.INVLD_FLG IS NULL)
                ORDER BY fee.CHRG_ITM_NM, fee.CHRG_DT;
            """,
            "手术记录": f"""
                SELECT DISTINCT 
                    o.INHOS_NO as O_INHOS_NO, o.OPRT_DT_TM, o.OPRT_NM, o.POPRT_DIAG_NM, o.OPRT_AFTR_DIAG_NM,
                    o.OPRT_PRCS_DSCPT, o.OPRT_WAY_DSCPT, o.HMHG_VLU,
                    f.INHOS_NO as F_INHOS_NO, f.TRTMT_TP_OPRT_TRTMT_FEE, f.TRTMT_TP_OPRT_FEE_ATHS_FEE, f.TRTMT_TP_OPRT_FEE_OPRT_FEE,
                    o.INVLD_FLG as O_INVLD_FLG, f.INVLD_FLG as F_INVLD_FLG
                FROM FACT_OPRT_EXEC_INFMT o
                LEFT JOIN FACT_MDC_RCD_HMPG_FEE f ON o.INHOS_NO = f.INHOS_NO
                WHERE o.INHOS_NO = '{self.inhos_no}';
            """,
            "收费": f"""
                SELECT 
                    fee.INHOS_NO, 
                    fee.CHRG_ITM_NM, 
                    fee.CHRG_ITM_CD, 
                    fee.CHRG_DT, 
                    fee.ITM_QTY, 
                    fee.ITM_UNT_PRICE, 
                    fee.ITM_UNT, 
                    fee.ITM_FEE,
                    (SELECT DISTINCT dtl.FEE_CGY_NM 
                     FROM FACT_INHOS_FEE_DTL dtl 
                     WHERE dtl.INHOS_NO = fee.INHOS_NO 
                       AND dtl.CHRG_ITM_CD = fee.CHRG_ITM_CD 
                     LIMIT 1) as FEE_CGY_NM,
                    fee.ORDER_NO, 
                    fee.ORDER_ITEM_CODE
                FROM FACT_FEEDTL_ORDER fee
                WHERE fee.INHOS_NO = '{self.inhos_no}';
            """,
            "医保": f"""
                SELECT DISTINCT INHOS_NO, MDCR_CGY_CD, MDCR_CGY_NM, INVLD_FLG
                FROM FACT_INHOS_FEE_STLMT
                WHERE INHOS_NO = '{self.inhos_no}';
            """,
            #select * from  FACT_OPRT_RCD where INHOS_NO='ZY010000477545'; 不需要字段映射的模块 SELECT *, INVLD_FLG FROM FACT_INHOS_CRS_RCD WHERE RCD_TP_NM = '医师查房记录' limit 1; AND INHOS_NO = '{self.inhos_no}';
            "入院记录": f"SELECT *, INVLD_FLG FROM FACT_INHOS_MDC_HTR_RCD WHERE INHOS_NO = '{self.inhos_no}' AND RCD_TP_NM NOT IN ('出院记录', '疾病诊断证明');",
            "首次病程记录": f"SELECT *, INVLD_FLG FROM FACT_INHOS_CRS_RCD WHERE RCD_TP_NM LIKE '%首次病程记录%' AND INHOS_NO = '{self.inhos_no}';",
            "上级医生查房记录": f"SELECT *, INVLD_FLG FROM FACT_INHOS_CRS_RCD WHERE RCD_TP_NM LIKE '%医师查房记录%' AND INHOS_NO = '{self.inhos_no}';",
            "日常病程记录": f"SELECT *, INVLD_FLG FROM FACT_INHOS_CRS_RCD WHERE RCD_TP_NM LIKE '%日常病程记录%' AND INHOS_NO = '{self.inhos_no}';",
            "化疗记录": f"SELECT *, INVLD_FLG FROM FACT_INHOS_CRS_RCD WHERE RCD_TP_NM LIKE '%化疗记录%' AND INHOS_NO = '{self.inhos_no}';",
            "出院记录": f"SELECT *, INVLD_FLG FROM FACT_INHOS_MDC_HTR_RCD WHERE RCD_TP_NM like '%出院记录%' AND INHOS_NO = '{self.inhos_no}';",
            "在院评估单": f"SELECT *, INVLD_FLG FROM FACT_INHOS_CRS_RCD WHERE RCD_TP_NM = '在院评估单' AND INHOS_NO = '{self.inhos_no}';",
            "手术记录详情": f"SELECT *, INVLD_FLG FROM FACT_OPRT_RCD WHERE INHOS_NO = '{self.inhos_no}';"
        }
# SELECT *, INVLD_FLG FROM FACT_INHOS_MDC_HTR_RCD WHERE RCD_TP_NM like '%出院记录%' AND INHOS_NO ='ZY010000474352';

    def execute_query(self, module):
        """执行查询"""
        query = self.module_queries.get(module)
        if not query:
            print(f"错误: 未找到模块 '{module}' 的查询语句")
            return []

        try:
            print(f"执行查询: {module}")

            # 创建游标
            with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
                # 执行SQL查询
                cursor.execute(query)
                # 获取所有结果
                results = cursor.fetchall()

            if not results:
                print(f"查询结果为空")
                return []

            # 确保正确打印查询结果
            print(f"原始查询返回 {len(results)} 条记录")

            # 检查是否有INVLD_FLG相关列
            filtered_records = []
            record_count = 0
            filtered_count = 0

            for record in results:
                record_count += 1
                # 检查记录中所有的INVLD_FLG字段
                is_valid = True
                for key in record.keys():
                    if 'INVLD_FLG' in key:  # 更宽松的匹配条件
                        # 获取值但不打印
                        invld_value = record[key]

                        # 尝试多种可能的值比较
                        if invld_value == 1 or invld_value == '1' or invld_value == 1.0:
                            is_valid = False
                            filtered_count += 1
                            break

                # 如果记录有效（所有INVLD_FLG=0或'0'等），则保留
                if is_valid:
                    # 创建新记录，但不包含INVLD_FLG字段
                    valid_record = {k: v for k, v in record.items() if 'INVLD_FLG' not in k}
                    filtered_records.append(valid_record)

            print(
                f"过滤前共 {record_count} 条记录，过滤掉 {filtered_count} 条无效记录，剩余 {len(filtered_records)} 条记录")
            return filtered_records

        except Exception as e:
            print(f"查询执行错误: {e}")
            # 对于特定的表不存在错误，给出更明确的提示
            if "doesn't exist" in str(e) and module == "护理记录":
                print(f"警告: {module}模块的某些表不存在，尝试使用备用查询方法")
                return []  # 或者调用一个备用方法
            return []

    def execute_nursing_query(self):
        """执行护理记录的分表查询，处理表不存在的情况"""
        result = {}

        # 查询主表FACT_MDC_RCD_HMPG (这个是必须的)
        try:
            main_query = f"""
                SELECT ADMN_DPT_NM, ADMN_DT_TM, DSCG_DT_TM, NM, GDR_NM, AGE, INHOS_NO, INVLD_FLG
                FROM FACT_MDC_RCD_HMPG
                WHERE INHOS_NO = '{self.inhos_no}';
            """

            with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
                # 执行SQL查询
                cursor.execute(main_query)
                # 获取所有结果
                main_results = cursor.fetchall()

            if main_results:
                # 检查主表的INVLD_FLG
                if main_results[0]['INVLD_FLG'] == 1:
                    print("主表INVLD_FLG=1，丢弃该记录")
                    return []

                # 复制所有非INVLD_FLG字段
                for col in main_results[0].keys():
                    if col != 'INVLD_FLG':
                        result[col] = main_results[0][col]
                print("主表查询成功")
            else:
                print("主表查询为空")
                return []
        except Exception as e:
            print(f"主表查询失败: {e}")
            # 主表必须存在，如果查询失败，返回空结果
            return []


        # 查询其他表，如果表不存在则设置相关字段为NULL
        tables_to_query = [
            {
                "name": "FACT_DSCG_RCD",
                "columns": ["ADMN_DIAG_WTM_DIAG_NM", "ADMN_DIAG_TCM_DSES_NM", "CDT_TNOVR_NM"],
                "query": f"""
                    SELECT 
                        ADMN_DIAG_WTM_DIAG_NM as DSCG_ADMN_DIAG_WTM_DIAG_NM, 
                        ADMN_DIAG_TCM_DSES_NM as DSCG_ADMN_DIAG_TCM_DSES_NM, 
                        CDT_TNOVR_NM, 
                        INHOS_NO as DSCG_INHOS_NO, 
                        INVLD_FLG
                    FROM FACT_DSCG_RCD 
                    WHERE INHOS_NO = '{self.inhos_no}';
                """
            },
            {
                "name": "FACT_TCM_MDC_RCD_HMPG",
                "columns": ["BED_NO"],
                "query": f"""
                    SELECT 
                        BED_NO, 
                        INHOS_NO as TCM_INHOS_NO, 
                        INVLD_FLG 
                    FROM FACT_TCM_MDC_RCD_HMPG 
                    WHERE INHOS_NO = '{self.inhos_no}';
                """
            },
            {
                "name": "FACT_ADMN_MDC_HTR_RCD",
                "columns": ["HGT", "WGT", "BRF_DSES_HST", "TPR", "PLS_RATE", "BRTH_FRQ", "STLC_PRS", "DTLC_PRS"],
                "query": f"""
                    SELECT 
                        HGT, WGT, BRF_DSES_HST, TPR, PLS_RATE, BRTH_FRQ, STLC_PRS, DTLC_PRS, 
                        INHOS_NO as ADMN_INHOS_NO, 
                        INVLD_FLG 
                    FROM FACT_ADMN_MDC_HTR_RCD 
                    WHERE INHOS_NO = '{self.inhos_no}';
                """
            },
            {
                "name": "FACT_DSCG_MDC_HTR_RCD",
                "columns": ["MAIN_TEST_RSLT", "LBRTR_EXAM_MAIN_CSTT", "ESPCL_EXAM", "PSTV_AXLR_EXAM_RSLT",
                            "OTHR_MDC_DSPST", "DSCG_CDT", "DIAG_TRTMT_PRCS_DSCPT", "DSCG_ODR"],
                "query": f"""
                    SELECT 
                        MAIN_TEST_RSLT, LBRTR_EXAM_MAIN_CSTT, ESPCL_EXAM, PSTV_AXLR_EXAM_RSLT, 
                        OTHR_MDC_DSPST, DSCG_CDT, DIAG_TRTMT_PRCS_DSCPT, DSCG_ODR, 
                        INHOS_NO as DSCG_MDC_INHOS_NO, 
                        INVLD_FLG 
                    FROM FACT_DSCG_MDC_HTR_RCD 
                    WHERE INHOS_NO = '{self.inhos_no}';
                """
            }
        ]
        # 执行各表查询
        # 执行各表查询
        for table_info in tables_to_query:
            try:
                with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
                    cursor.execute(table_info["query"])
                    table_results = cursor.fetchall()

                if table_results:
                    # 检查INVLD_FLG
                    if table_results[0]['INVLD_FLG'] == 1:
                        print(f"{table_info['name']}表INVLD_FLG=1，丢弃该表数据")
                        continue

                    for col in table_results[0].keys():
                        if col == 'INVLD_FLG' or col.endswith('_INHOS_NO'):
                            continue

                        mapped_col = col
                        # 如果是DSCG_前缀的列名，需要映射回原始列名以匹配配置
                        if col.startswith("DSCG_"):
                            mapped_col = col[5:]  # 去掉DSCG_前缀

                        result[mapped_col] = table_results[0][col]
                    print(f"{table_info['name']}表查询成功")
                else:
                    print(f"{table_info['name']}表查询结果为空")
            except Exception as e:
                print(f"{table_info['name']}表查询失败: {e}")
                # 设置表中字段为NULL
                for col in table_info["columns"]:
                    result[col] = None

        # 将结果转换为DataFrame并转换为字典列表
        if result:
            # 不直接创建DataFrame，而是先确保没有重复的键
            unique_result = {}
            for key, value in result.items():
                if key not in unique_result and key != 'INVLD_FLG' and not key.endswith('_INHOS_NO'):
                    unique_result[key] = value

            df = pd.DataFrame([unique_result])
            df = self.ensure_unique_columns(df)

            return df.to_dict('records')
        return []

    # 在MedicalDataProcessor类中
    def process_modules(self, modules=None):
            """处理指定模块"""
            if modules is None:
                modules = ["病理", "医嘱", "护理记录", "检查", "检验", "诊断", "诊断信息", "手术记录", "在院评估单", "收费", "医保", "用药信息"]

            result = {}
            list_modules = ["病理", "医嘱", "护理记录", "检查", "检验", "诊断", "诊断信息", "收费", "医保", "用药信息"]  # 从这里移除了"手术记录"，替换了"治疗用药"和"手术用药"为"用药信息"
            for module in modules:
                if module == "护理记录":
                    # 使用分表查询处理护理记录，并传入生命体征数据
                    records = self.execute_nursing_query()
                    result[module] = self.converter.process_nursing_records(records,
                                                                            self.extracted_vital_signs) if records else []
                elif module == "手术记录":
                    # 使用新方法处理手术记录
                    result[module] = self.process_operation_record()
                elif module in list_modules:
                    records = self.execute_query(module)
                    result[module] = self.converter.process_result(module, records) if records else []
                elif module == "在院评估单":
                    records = self.execute_query(module)
                    result[module] = self.converter.process_assessment_form(records)

            return result

    def test_llm_connection(self):
        """测试大模型连接是否正常工作"""
        print("开始测试大模型连接...")
        test_prompt = "请回答一个简单的问题：1+1等于几？请直接回答数字。"
        response = chat_method(test_prompt)
        print(f"大模型返回: {response}")
        print("测试完成")
        return response

    def extract_admission_record(self, records):
        """使用大模型提取入院记录内容，并判断内容是否完整"""
        # 默认返回结果
        default_result = {
            "创建时间": "xxx",
            "患者一般情况": "文本中未提及该内容",
            "主诉": "文本中未提及该内容",
            "现病史": "文本中未提及该内容",
            "既往史": "文本中未提及该内容",
            "个人史": "文本中未提及该内容",
            "婚育史": "文本中未提及该内容",
            "月经史": "文本中未提及该内容",
            "家族史": "文本中未提及该内容",
            "体格检查": "文本中未提及该内容",
            "专科情况": "文本中未提及该内容",
            "辅助检查": "文本中未提及该内容",
            "初步诊断": "文本中未提及该内容",
            "更正诊断": "文本中未提及该内容",
            "FIGO分期": "文本中未提及该内容",
            "TNM分期": "文本中未提及该内容",
            "其他肿瘤分期": "文本中未提及该内容",
            "主治医师48小时诊断": "文本中未提及该内容"
        }

        if not records:
            print("警告: 未找到入院记录数据")
            return {"内容缺失": True, "原因": "未找到入院记录数据"}

        # 提取DCMT_CTT字段内容和时间
        record_time = "xxx"
        dcmt_content = ""

        for record in records:
            # 检查INVLD_FLG
            if 'INVLD_FLG' in record and record['INVLD_FLG'] == 1:
                print("入院记录INVLD_FLG=1，丢弃该记录")
                continue

            # 提取记录时间 - 优先使用CRT_TM，然后RCD_DT
            if "CRT_TM" in record and record["CRT_TM"]:
                record_time = self.converter.format_date(record["CRT_TM"])
                print(f"入院记录使用CRT_TM作为创建时间: {record_time}")
            elif "RCD_DT" in record and record["RCD_DT"]:
                record_time = self.converter.format_date(record["RCD_DT"])
                print(f"入院记录使用RCD_DT作为创建时间: {record_time}")

            # 提取DCMT_CTT内容
            if "DCMT_CTT" in record and record["DCMT_CTT"]:
                dcmt_content = record["DCMT_CTT"]
                print(f"成功提取DCMT_CTT内容，长度: {len(dcmt_content)}")
                break

        if not dcmt_content:
            print("错误: 未找到入院记录DCMT_CTT内容")
            return {"内容缺失": True, "原因": "未找到入院记录内容"}

        # 使用大模型提取信息 - 修改提示词，让大模型判断内容完整性
        prompt = f"""
    请根据以下电子病历文本，提取入院记录的关键信息：

    {dcmt_content}

    给你的文本是有很多内容的，可能包括了入院记录信息，出院记录信息等。入院记录信息会包含主诉、现病史、既往史、个人史、婚育史、家族史、月经史、体格检查等内容，如果没有找到涵盖这些内容的文字，那就意味着缺少入院记录。通过找到这些内容，你可以分辨文本中哪些是入院记录信息。

    请从文本中提取以下入院记录的字段信息：
    - 文档记录时间（文档中显示的时间，通常在文档开头或末尾，格式为年-月-日或年-月-日 时:分等。注意要找到哪个是入院记录，并定位它的时间）
    - 患者一般情况
    - 主诉
    - 现病史
    - 既往史
    - 个人史
    - 婚育史
    - 月经史
    - 家族史
    - 体格检查
    - 专科情况
    - 辅助检查
    - 初步诊断
    - 更正诊断
    - FIGO分期
    - TNM分期
    - 其他肿瘤分期
    - 主治医师48小时诊断

    同时，请判断文本中是否存在完整的入院记录：
    1. 如果文本中包含主诉、现病史、既往史和体格检查等关键信息，说明入院记录比较完整
    2. 如果这些关键信息大多数缺失，说明可能不是完整的入院记录

    
    请按照以下格式返回JSON：
    {{
      "内容完整性判断": "完整" 或 "缺失",
      "缺失字段": ["字段1", "字段2", ...] (如果判断为缺失，列出关键缺失字段),
      "文档记录时间": "提取到的时间或'文本中未提及该内容'",
      "患者一般情况": "文本内容或'文本中未提及该内容'",
      "主诉": "文本内容或'文本中未提及该内容'",
      "现病史": "文本内容或'文本中未提及该内容'",
      "既往史": "文本内容或'文本中未提及该内容'",
      "个人史": "文本内容或'文本中未提及该内容'",
      "婚育史": "文本内容或'文本中未提及该内容'",
      "月经史": "文本内容或'文本中未提及该内容'",
      "家族史": "文本内容或'文本中未提及该内容'",
      "体格检查": "文本内容或'文本中未提及该内容'",
      "专科情况": "文本内容或'文本中未提及该内容'",
      "辅助检查": "文本内容或'文本中未提及该内容'",
      "初步诊断": "文本内容或'文本中未提及该内容'",
      "更正诊断": "文本内容或'文本中未提及该内容'",
      "FIGO分期": "文本内容或'文本中未提及该内容'",
      "TNM分期": "文本内容或'文本中未提及该内容'",
      "其他肿瘤分期": "文本内容或'文本中未提及该内容'",
      "主治医师48小时诊断": "文本内容或'文本中未提及该内容'"
    }}

    特别注意：1、判断内容完整性非常重要，重点关注主诉、现病史、既往史、体格检查这四个关键字段是否存在有效内容。
    2、文本中若有与诊疗无关的个人敏感信息（包括：姓名，电话，邮箱，身份证号，地址等），将其隐藏为***，如文本“现住浙江省杭州市/生于浙江省杭州市”，将其隐藏为“现住***/生于***”，不要隐去性别、年龄等和诊疗有关的关键个人信息
        """

        print("调用大模型提取信息并判断入院记录完整性...")
        response = multi_model_api.chat_method_for_module("入院记录", prompt)
        print(f"大模型响应长度: {len(response)}")

        # 尝试解析JSON
        try:
            # 找出JSON的范围并解析
            json_start = response.find("{")
            json_end = response.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]

                # 清理和解析JSON
                json_str = json_str.replace("'", '"').replace('\n', ' ')
                extracted_data = json.loads(json_str)

                # 检查内容完整性判断
                completeness = extracted_data.get("内容完整性判断", "")
                if completeness == "缺失":
                    missing_fields = extracted_data.get("缺失字段", [])
                    reason = f"入院记录关键信息缺失: {', '.join(missing_fields)}"
                    print(f"警告: {reason}")
                    return {"内容缺失": True, "原因": reason}

                # 内容完整性判断为完整或未提供判断，继续处理
                result = default_result.copy()

                # 从提取的数据中获取时间
                doc_time = extracted_data.get("文档记录时间", "文本中未提及该内容")
                if doc_time and doc_time != "文本中未提及该内容":
                    result["时间"] = doc_time
                else:
                    result["时间"] = "文本中未提及该内容"
                
                # 添加数据库创建时间
                result["创建时间"] = record_time

                # 复制其他字段
                for key in default_result:
                    if key not in ["时间", "创建时间"] and key in extracted_data:
                        result[key] = extracted_data[key]

                return result

        except Exception as e:
            print(f"处理大模型响应时出错: {e}")

        # 如果无法解析或出错，尝试进行简单内容完整性判断
        # 计算有效内容的字段数量
        valid_content_count = sum(1 for item in default_result.values() if item != "文本中未提及该内容")

        if valid_content_count < 4:  # 如果大部分内容都缺失
            return {"内容缺失": True, "原因": "无法提取足够的入院记录内容"}

        # 返回默认结果
        default_result["时间"] = record_time
        return default_result

    def extract_first_course_record(self, records):
        """使用大模型提取首次病程记录内容 - 专注于DCMT_CTT字段"""
        # 默认返回结果
        default_result = {
            "创建时间": "xxx",
            "病例特点": "文本中未提及该内容",
            "初步诊断": "文本中未提及该内容",
            "诊断依据": "文本中未提及该内容",
            "鉴别诊断": "文本中未提及该内容",
            "拟诊讨论": "文本中未提及该内容",
            "诊疗计划": "文本中未提及该内容"
        }

        if not records:
            return default_result

        # 提取DCMT_CTT字段内容和时间
        record_time = "xxx"
        dcmt_content = ""

        for record in records:
            # 检查INVLD_FLG
            if 'INVLD_FLG' in record and record['INVLD_FLG'] == 1:
                print("首次病程记录INVLD_FLG=1，丢弃该记录")
                continue

            # 提取记录时间 - 优先使用CRT_TM，然后RCD_DT
            if "CRT_TM" in record and record["CRT_TM"]:
                record_time = self.converter.format_date(record["CRT_TM"])
                print(f"首次病程记录使用CRT_TM作为创建时间: {record_time}")
            elif "RCD_DT" in record and record["RCD_DT"]:
                record_time = self.converter.format_date(record["RCD_DT"])
                print(f"首次病程记录使用RCD_DT作为创建时间: {record_time}")

            # 提取DCMT_CTT内容
            if "DCMT_CTT" in record and record["DCMT_CTT"]:
                dcmt_content = record["DCMT_CTT"]
                print(f"成功提取首次病程记录DCMT_CTT内容，长度: {len(dcmt_content)}")
                break

        if not dcmt_content:
            print("未找到首次病程记录DCMT_CTT内容")
            default_result["时间"] = record_time
            return default_result

        # 使用大模型提取信息
        prompt = f"""
请根据以下电子病历文本（首次病程记录），提取关键信息：

{dcmt_content}

请从文本中提取以下字段信息：
- 文档记录时间（文档中显示的时间，通常在文档开头，格式为年-月-日或年-月-日 时:分等）
- 病例特点（患者的主要临床特征和主要问题的总结）
- 初步诊断（医生的初步诊断意见）
- 诊断依据（支持诊断的证据和理由）
- 鉴别诊断（需要排除的其他可能诊断）
- 诊疗计划（接下来的治疗和检查计划）
- 拟诊讨论（讨论的诊断意见）
你必须严格按照以下格式返回JSON，不要添加任何其他说明：
{{
  "文档记录时间": "提取到的时间或'文本中未提及该内容'",
  "病例特点": "文本内容或'文本中未提及该内容'",
  "初步诊断": "文本内容或'文本中未提及该内容'",
  "诊断依据": "文本内容或'文本中未提及该内容'",
  "鉴别诊断": "文本内容或'文本中未提及该内容'",
  "诊疗计划": "文本内容或'文本中未提及该内容'",
  "拟诊讨论": "文本内容或'文本中未提及该内容'",
}}

特别注意：1、仔细寻找文档中的任何日期时间信息，特别是文档开头部分的时间戳。首次病程记录的时间通常会显示在文档顶部。
2、如果文本中未提及某个字段的内容，则该字段的值应为"文本中未提及该内容"。仔细检查文本中是否有类似"病例特点"、"初步诊断"等直接标题，如果有则直接提取内容。
3、文本中若有与诊疗无关的个人敏感信息（包括：姓名，电话，邮箱，身份证号，地址等），将其隐藏为***，如文本“现住浙江省杭州市/生于浙江省杭州市”包含地址信息，将其隐藏为“现住***/生于***”，不要隐去性别、年龄等和诊疗有关的关键个人信息
        """

        print("调用大模型提取首次病程记录信息...")
        response = multi_model_api.chat_method_for_module("首次病程记录", prompt)
        print(f"大模型响应长度: {len(response)}")

        # 尝试解析JSON
        try:
            # 找出JSON的范围
            json_start = response.find("{")
            json_end = response.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                # 提取JSON部分
                json_str = response[json_start:json_end]
                print(f"提取到JSON字符串，长度: {len(json_str)}")

                # 清理和格式化JSON字符串
                json_str = json_str.replace("'", '"')  # 单引号替换为双引号
                json_str = json_str.replace('\n', ' ')  # 移除换行符

                try:
                    # 解析JSON
                    extracted_data = json.loads(json_str)
                    print("成功解析首次病程记录JSON")

                    # 合并结果
                    result = default_result.copy()

                    # 从提取的数据中获取时间
                    doc_time = extracted_data.get("文档记录时间", "文本中未提及该内容")
                    if doc_time and doc_time != "文本中未提及该内容":
                        result["时间"] = doc_time
                    else:
                        result["时间"] = "文本中未提及该内容"
                    
                    # 添加数据库创建时间
                    result["创建时间"] = record_time

                    # 复制其他字段
                    for key in extracted_data:
                        if key not in ["文档记录时间", "创建时间"] and key in result:
                            result[key] = extracted_data[key]

                    return result
                except json.JSONDecodeError as e:
                    print(f"首次病程记录JSON解析失败: {e}")

                    # 尝试修复JSON格式
                    try:
                        # 确保键使用双引号
                        json_str = re.sub(r'([{,])\s*([a-zA-Z0-9_\u4e00-\u9fa5]+)\s*:', r'\1"\2":', json_str)
                        # 确保值使用双引号（如果不是数字）
                        json_str = re.sub(r':\s*([^",\{\}\[\]\d][^",\{\}\[\]]*[^",\{\}\[\]\d])\s*([,\}])', r':"\1"\2',
                                          json_str)

                        # 再次尝试解析
                        extracted_data = json.loads(json_str)
                        print("修复后成功解析首次病程记录JSON")

                        # 合并结果
                        result = default_result.copy()

                        # 从提取的数据中获取时间，如果没有则使用数据库记录时间
                        doc_time = extracted_data.get("文档记录时间", "文本中未提及该内容")
                        if doc_time and doc_time != "文本中未提及该内容":
                            result["时间"] = doc_time
                        else:
                            result["时间"] = record_time

                        # 复制其他字段
                        for key in extracted_data:
                            if key != "文档记录时间" and key in result:
                                result[key] = extracted_data[key]

                        return result
                    except Exception as e2:
                        print(f"修复首次病程记录JSON后仍然解析失败: {e2}")
            else:
                print("未在首次病程记录响应中找到JSON结构")
        except Exception as e:
            print(f"处理首次病程记录大模型响应时出错: {e}")

        # 如果所有尝试都失败，返回默认结果
        default_result["时间"] = record_time
        return default_result

    def extract_ward_round_records(self, records, physician_type):
        """
        Extract the first ward round record for a specific physician type

        Args:
            records: List of ward round records
            physician_type: "主治医师" or "主任医师"

        Returns:
            Dictionary with extracted information
        """
        # Default result templates based on physician type
        if physician_type == "主治医师":
            default_result = {
                "时间": "xxx",
                "主治医生查房": "文本中未提及该内容",
                "诊断": "文本中未提及该内容",
                "诊断依据": "文本中未提及该内容",
                "鉴别诊断": "文本中未提及该内容",
                "诊疗计划": "文本中未提及该内容",
                "补充病史和体征": "文本中未提及该内容"
            }
        else:  # 主任医师
            default_result = {
                "时间": "xxx",
                "主任医生查房": "文本中未提及该内容",
                "诊疗计划": "文本中未提及该内容",
                "注意事项": "文本中未提及该内容",
                "补充病史与体征": "文本中未提及该内容",
                "对病情的分析": "文本中未提及该内容",
                "诊疗意见": "文本中未提及该内容"
            }

        if not records:
            print(f"未找到{physician_type}查房记录")
            return default_result

        # 直接从文档内容中解析记录和日期
        filtered_records = []
        from datetime import datetime
        import re

        for record in records:
            # 检查INVLD_FLG
            if 'INVLD_FLG' in record and record['INVLD_FLG'] == 1:
                print(f"{physician_type}查房记录INVLD_FLG=1，丢弃该记录")
                continue

            if "DCMT_CTT" in record and record["DCMT_CTT"]:
                content = record["DCMT_CTT"]

                # 检查是否包含特定医师类型的查房记录
                if physician_type in content and "查房记录" in content:
                    # 尝试从文档内容开头提取日期时间
                    date_match = re.search(r'(\d{4}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{1,2})', content)
                    if date_match:
                        try:
                            doc_date = datetime.strptime(date_match.group(1), "%Y-%m-%d %H:%M")
                            print(f"从文档内容中提取到日期: {doc_date} - {physician_type}查房记录")
                            record["doc_date"] = doc_date
                            filtered_records.append(record)
                        except Exception as e:
                            print(f"日期解析错误: {e}")
                            # 如果无法解析文档内容中的日期，则使用数据库时间字段 - 优先CRT_TM，然后RCD_DT
                            db_time_field = None
                            if "CRT_TM" in record and record["CRT_TM"]:
                                db_time_field = record["CRT_TM"]
                                print(f"{physician_type}查房记录使用CRT_TM作为创建时间")
                            elif "RCD_DT" in record and record["RCD_DT"]:
                                db_time_field = record["RCD_DT"]
                                print(f"{physician_type}查房记录使用RCD_DT作为创建时间")
                            
                            if db_time_field:
                                try:
                                    if isinstance(db_time_field, datetime):
                                        record["doc_date"] = db_time_field
                                    else:
                                        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y%m%d%H%M%S", "%Y%m%d"]:
                                            try:
                                                record["doc_date"] = datetime.strptime(str(db_time_field), fmt)
                                                break
                                            except ValueError:
                                                continue
                                    filtered_records.append(record)
                                except Exception as e2:
                                    print(f"数据库时间字段解析错误: {e2}")
                    else:
                        # 如果在内容中找不到日期，使用记录日期
                        if "RCD_DT" in record and record["RCD_DT"]:
                            try:
                                if isinstance(record["RCD_DT"], datetime):
                                    record["doc_date"] = record["RCD_DT"]
                                else:
                                    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y%m%d%H%M%S", "%Y%m%d"]:
                                        try:
                                            record["doc_date"] = datetime.strptime(str(record["RCD_DT"]), fmt)
                                            break
                                        except ValueError:
                                            continue
                                filtered_records.append(record)
                            except Exception as e:
                                print(f"记录日期解析错误: {e}")

        if not filtered_records:
            print(f"未找到包含{physician_type}的查房记录")
            return default_result

        # 按日期排序
        sorted_records = sorted(filtered_records, key=lambda x: x.get("doc_date", datetime.max))

        # 输出排序结果进行验证
        print(f"找到 {len(sorted_records)} 条{physician_type}查房记录")
        for idx, rec in enumerate(sorted_records[:3]):  # 显示前3条记录用于调试
            dt = rec.get("doc_date", "未知")
            content_preview = rec.get("DCMT_CTT", "")[:50] if rec.get("DCMT_CTT") else "无内容"
            print(f"Record {idx}: Date = {dt}, Content = {content_preview}...")

        if not sorted_records:
            print(f"排序后未找到{physician_type}查房记录")
            return default_result

        # 获取最早的记录
        earliest_record = sorted_records[0]
        # 使用文档中提取的日期或记录日期格式化
        record_time = self.converter.format_date(earliest_record.get("doc_date", earliest_record.get("RCD_DT", "")))
        dcmt_content = earliest_record.get("DCMT_CTT", "")

        print(f"找到最早的{physician_type}查房记录，时间: {record_time}")
        print(f"内容预览: {dcmt_content[:100]}...")

        if not dcmt_content:
            print(f"最早的{physician_type}查房记录内容为空")
            default_result["时间"] = record_time
            return default_result
        # Define LLM prompt based on physician type
        if physician_type == "主治医师":
            prompt = f"""
请根据以下电子病历文本（主治医师查房记录），提取关键信息：

{dcmt_content}

请从文本中提取以下字段信息：
- 文档记录时间（文档中显示的时间，通常在文档开头，格式为年-月-日或年-月-日 时:分等）
- 主治医生查房（这段内容不做抽取，而是直接引用文本的全部原始内容。注意是直接引用就可以，不要写'文本中未提及该内容'）
- 诊断（主治医生的诊断意见）
- 诊断依据（支持诊断的证据和理由）
- 鉴别诊断（需要排除的其他可能诊断）
- 诊疗计划（接下来的治疗和检查计划）
- 补充病史和体征（补充的病史信息和体征发现）

你必须严格按照以下格式返回JSON，不要添加任何其他说明：
{{
  "文档记录时间": "提取到的时间或'文本中未提及该内容'",
  "主治医生查房": "文本内容或'文本中未提及该内容'",
  "诊断": "文本内容或'文本中未提及该内容'",
  "诊断依据": "文本内容或'文本中未提及该内容'",
  "鉴别诊断": "文本内容或'文本中未提及该内容'",
  "诊疗计划": "文本内容或'文本中未提及该内容'",
  "补充病史和体征": "文本内容或'文本中未提及该内容'"
}}

特别注意：1、仔细寻找文档中的任何日期时间信息，特别是文档开头部分的时间戳。查房记录的时间通常会显示在文档顶部。示例：2022-11-19 08:57。
2、如果文本中未提及某个字段的内容，则该字段的值应为"文本中未提及该内容"。
3、文本中若有与诊疗无关的个人敏感信息（包括：姓名，电话，邮箱，身份证号，地址等），将其隐藏为***，如文本“现住浙江省杭州市/生于浙江省杭州市”包含地址信息，将其隐藏为“现住***/生于***”，不要隐去性别、年龄等和诊疗有关的关键个人信息
            """
        else:  # 主任医师
            prompt = f"""
请根据以下电子病历文本（主任医师查房记录），提取关键信息：

{dcmt_content}

请从文本中提取以下字段信息：
- 文档记录时间（文档中显示的时间，通常在文档开头，格式为年-月-日或年-月-日 时:分等）
- 主任医生查房（这段内容不做抽取，而是直接引用文本的全部原始内容。注意是直接引用就可以，不要写'文本中未提及该内容'）
- 诊疗计划（接下来的治疗和检查计划）
- 注意事项（需要特别注意的问题）
- 补充病史与体征（补充的病史信息和体征发现）
- 对病情的分析（对疾病情况的分析和评估）
- 诊疗意见（主任医生的治疗建议和意见）

你必须严格按照以下格式返回JSON，不要添加任何其他说明：
{{
  "文档记录时间": "提取到的时间或'文本中未提及该内容'",
  "主任医生查房": "文本内容或'文本中未提及该内容'",
  "诊疗计划": "文本内容或'文本中未提及该内容'",
  "注意事项": "文本内容或'文本中未提及该内容'",
  "补充病史与体征": "文本内容或'文本中未提及该内容'",
  "对病情的分析": "文本内容或'文本中未提及该内容'",
  "诊疗意见": "文本内容或'文本中未提及该内容'"
}}

特别注意：1、仔细寻找文档中的任何日期时间信息，特别是文档开头部分的时间戳。查房记录的时间通常会显示在文档顶部。示例：2022-11-24 09:15。
2、如果文本中未提及某个字段的内容，则该字段的值应为"文本中未提及该内容"。
3、文本中若有与诊疗无关的个人敏感信息（包括：姓名，电话，邮箱，身份证号，地址等），将其隐藏为***，如文本“现住浙江省杭州市/生于浙江省杭州市”包含地址信息，将其隐藏为“现住***/生于***”，不要隐去性别、年龄等和诊疗有关的关键个人信息
            """

        print(f"调用大模型提取{physician_type}查房记录信息...")
        response = chat_method(prompt)
        print(f"大模型响应长度: {len(response)}")

        # Parse JSON response
        try:
            # Find JSON range
            json_start = response.find("{")
            json_end = response.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                # Extract JSON part
                json_str = response[json_start:json_end]
                print(f"提取到JSON字符串，长度: {len(json_str)}")

                # Clean and format JSON string
                json_str = json_str.replace("'", '"')  # Replace single quotes with double quotes
                json_str = json_str.replace('\n', ' ')  # Remove newlines

                try:
                    # Parse JSON
                    extracted_data = json.loads(json_str)
                    print(f"成功解析{physician_type}查房记录JSON")

                    # Merge results
                    result = default_result.copy()

                    # 从提取的数据中获取时间，如果没有则使用数据库记录时间
                    doc_time = extracted_data.get("文档记录时间", "文本中未提及该内容")
                    if doc_time and doc_time != "文本中未提及该内容":
                        result["时间"] = doc_time
                    else:
                        result["时间"] = record_time

                    # 复制其他字段
                    for key in extracted_data:
                        if key != "文档记录时间" and key in result:
                            result[key] = extracted_data[key]

                    return result
                except json.JSONDecodeError as e:
                    print(f"{physician_type}查房记录JSON解析失败: {e}")

                    # Try to fix JSON format
                    try:
                        # Ensure keys use double quotes
                        json_str = re.sub(r'([{,])\s*([a-zA-Z0-9_\u4e00-\u9fa5]+)\s*:', r'\1"\2":', json_str)
                        # Ensure values use double quotes (if not a number)
                        json_str = re.sub(r':\s*([^",\{\}\[\]\d][^",\{\}\[\]]*[^",\{\}\[\]\d])\s*([,\}])', r':"\1"\2',
                                          json_str)

                        # Try parsing again
                        extracted_data = json.loads(json_str)
                        print(f"修复后成功解析{physician_type}查房记录JSON")

                        # Merge results
                        result = default_result.copy()

                        # 从提取的数据中获取时间，如果没有则使用数据库记录时间
                        doc_time = extracted_data.get("文档记录时间", "文本中未提及该内容")
                        if doc_time and doc_time != "文本中未提及该内容":
                            result["时间"] = doc_time
                        else:
                            result["时间"] = record_time

                        # 复制其他字段
                        for key in extracted_data:
                            if key != "文档记录时间" and key in result:
                                result[key] = extracted_data[key]

                        return result
                    except Exception as e2:
                        print(f"修复{physician_type}查房记录JSON后仍然解析失败: {e2}")
            else:
                print(f"未在{physician_type}查房记录响应中找到JSON结构")
        except Exception as e:
            print(f"处理{physician_type}查房记录大模型响应时出错: {e}")

        # If all attempts fail, return default result
        default_result["时间"] = record_time
        return default_result

    def extract_discharge_record(self, records):
        """提取出院记录内容 - 直接提取出院诊断，其余字段仍使用大模型"""
        # 默认返回结果
        default_result = {
            "创建时间": "xxx",
            "入院日期": "文本中未提及该内容",
            "出院日期": "文本中未提及该内容",
            "入院诊断": "文本中未提及该内容",
            "出院诊断": "文本中未提及该内容",
            "入院情况": "文本中未提及该内容",
            "诊疗经过": "文本中未提及该内容",
            "合并症": "文本中未提及该内容",
            "出院情况": "文本中未提及该内容",
            "出院医嘱": "文本中未提及该内容",
            "治疗结果": "文本中未提及该内容",
            "术后病理pTNM分期": "文本中未提及该内容",
        }

        if not records:
            return default_result

        # 提取DCMT_CTT字段内容和时间
        record_time = "xxx"
        dcmt_content = ""

        for record in records:
            # 检查INVLD_FLG
            if 'INVLD_FLG' in record and record['INVLD_FLG'] == 1:
                print("出院记录INVLD_FLG=1，丢弃该记录")
                continue

            # 提取记录时间 - 优先使用CRT_TM，然后RCD_DT
            if "CRT_TM" in record and record["CRT_TM"]:
                record_time = self.converter.format_date(record["CRT_TM"])
                print(f"出院记录使用CRT_TM作为创建时间: {record_time}")
            elif "RCD_DT" in record and record["RCD_DT"]:
                record_time = self.converter.format_date(record["RCD_DT"])
                print(f"出院记录使用RCD_DT作为创建时间: {record_time}")

            # 提取DCMT_CTT内容
            if "DCMT_CTT" in record and record["DCMT_CTT"]:
                dcmt_content = record["DCMT_CTT"]
                print(f"成功提取出院记录DCMT_CTT内容，长度: {len(dcmt_content)}")
                break

        if not dcmt_content:
            print("未找到出院记录DCMT_CTT内容")
            default_result["时间"] = record_time
            return default_result

        # 直接从文本中提取出院诊断
        discharge_diagnosis = self.extract_discharge_diagnosis_first_item(dcmt_content)
        
        # 使用大模型提取其他信息
        prompt = f"""
    请根据以下电子病历文本（出院记录），提取除了出院诊断以外的关键信息：
    {dcmt_content}
    请从文本中提取以下字段信息：
    - 文档记录时间（文档中显示的时间，通常在文档末尾，格式为年-月-日或年-月-日 时:分等）
    - 入院日期（患者入院的具体日期）
    - 出院日期（患者出院的具体日期）
    - 入院诊断（患者入院时的诊断结果）
    - 入院情况（患者入院时的状态和症状）
    - 诊疗经过（住院期间的治疗过程和检查）
    - 合并症（患者同时存在的其他疾病）
    - 出院情况（患者出院时的状态）
    - 出院医嘱（出院后的用药、复诊等建议）
    - 治疗结果（治疗后的效果）
    - 术后病理pTNM分期（术后病理的pTNM分期）

    你必须严格按照以下格式返回JSON，不要添加任何其他说明：
    {{
      "文档记录时间": "提取到的时间或'文本中未提及该内容'",
      "入院日期": "文本内容或'文本中未提及该内容'",
      "出院日期": "文本内容或'文本中未提及该内容'",
      "入院诊断": "文本内容或'文本中未提及该内容'",
      "出院诊断": "文本内容或'文本中未提及该内容'",
      "入院情况": "文本内容或'文本中未提及该内容'",
      "诊疗经过": "文本内容或'文本中未提及该内容'",
      "合并症": "文本内容或'文本中未提及该内容'",
      "出院情况": "文本内容或'文本中未提及该内容'",
      "出院医嘱": "文本内容或'文本中未提及该内容'",
      "治疗结果": "文本内容或'文本中未提及该内容'",
      "术后病理pTNM分期": "文本内容或'文本中未提及该内容'"
    }}

    特别注意：1、仔细寻找文档中的任何日期时间信息，特别是文档末尾部分的时间戳。出院记录的文档时间通常会在医生签字附近。
    2、如果文本中未提及某个字段的内容，则该字段的值应为"文本中未提及该内容"。
    3、文本中若有与诊疗无关的个人敏感信息（包括：姓名，电话，邮箱，身份证号，地址等），将其隐藏为***，如文本“现住浙江省杭州市/生于浙江省杭州市”包含地址信息，将其隐藏为“现住***/生于***”，不要隐去性别、年龄等和诊疗有关的关键个人信息。
        """

        print("调用大模型提取出院记录信息...")
        response = chat_method(prompt)
        print(f"大模型响应长度: {len(response)}")

        # 解析JSON并构建结果
        try:
            # 找出JSON的范围
            json_start = response.find("{")
            json_end = response.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                # 提取JSON部分
                json_str = response[json_start:json_end]
                # 清理和格式化JSON字符串
                json_str = json_str.replace("'", '"')
                json_str = json_str.replace('\n', ' ')

                try:
                    # 解析JSON
                    extracted_data = json.loads(json_str)
                    print("成功解析出院记录JSON")

                    # 合并结果
                    result = default_result.copy()

                    # 从提取的数据中获取时间
                    doc_time = extracted_data.get("文档记录时间", "文本中未提及该内容")
                    if doc_time and doc_time != "文本中未提及该内容":
                        result["时间"] = doc_time
                    else:
                        result["时间"] = "文本中未提及该内容"
                    
                    # 添加数据库创建时间
                    result["创建时间"] = record_time

                    # 复制其他字段
                    for key in extracted_data:
                        if key not in ["文档记录时间", "创建时间"] and key in result:
                            result[key] = extracted_data[key]

                    # 设置直接提取的出院诊断
                    result["出院诊断"] = discharge_diagnosis

                    return result
                except json.JSONDecodeError as e:
                    # [保留原来的错误处理代码...]
                    print(f"出院记录JSON解析失败: {e}")
                    try:
                        # 尝试修复JSON格式
                        json_str = re.sub(r'([{,])\s*([a-zA-Z0-9_\u4e00-\u9fa5]+)\s*:', r'\1"\2":', json_str)
                        json_str = re.sub(r':\s*([^",\{\}\[\]\d][^",\{\}\[\]]*[^",\{\}\[\]\d])\s*([,\}])', r':"\1"\2',
                                          json_str)
                        extracted_data = json.loads(json_str)

                        # [合并结果的代码同上]
                        result = default_result.copy()
                        doc_time = extracted_data.get("文档记录时间", "文本中未提及该内容")
                        if doc_time and doc_time != "文本中未提及该内容":
                            result["时间"] = doc_time
                        else:
                            result["时间"] = record_time
                        for key in extracted_data:
                            if key != "文档记录时间" and key in result:
                                result[key] = extracted_data[key]
                        result["出院诊断"] = discharge_diagnosis
                        return result
                    except Exception as e2:
                        print(f"修复出院记录JSON后仍然解析失败: {e2}")
            else:
                print("未在出院记录响应中找到JSON结构")
        except Exception as e:
            print(f"处理出院记录大模型响应时出错: {e}")

        # 如果所有尝试都失败，返回只有出院诊断的默认结果
        default_result["时间"] = record_time
        default_result["出院诊断"] = discharge_diagnosis
        return default_result

    def _fix_operation_json(self, json_str):
        """专门修复手术记录JSON格式的函数"""
        try:
            # 基础清理
            fixed = json_str.strip()
            
            # 移除可能的BOM标记
            if fixed.startswith('\ufeff'):
                fixed = fixed[1:]
            
            # 确保是有效的JSON结构
            if not fixed.startswith('{') or not fixed.endswith('}'):
                return None
            
            # 替换单引号为双引号
            fixed = fixed.replace("'", '"')
            
            # 移除换行符和制表符
            fixed = fixed.replace('\n', ' ').replace('\t', ' ').replace('\r', ' ')
            
            # 确保键名用双引号包围
            fixed = re.sub(r'([{,])\s*([a-zA-Z0-9_\u4e00-\u9fa5]+)\s*:', r'\1"\2":', fixed)
            
            # 处理值中的特殊字符
            fixed = re.sub(r':\s*([^"][^,}]*[^"])\s*([,}])', r':"\1"\2', fixed)
            
            # 处理可能的转义字符
            fixed = fixed.replace('\\"', '"').replace('\\n', ' ').replace('\\t', ' ')
            
            # 移除多余的空格
            fixed = re.sub(r'\s+', ' ', fixed)
            
            # 验证JSON格式
            json.loads(fixed)
            return fixed
            
        except Exception as e:
            print(f"JSON修复失败: {e}")
            return None
    def extract_operation_record(self, records):
        """使用大模型提取手术记录内容"""
        # 默认返回结果
        default_result = {
            "创建时间": "xxx",
            "手术日期": "文本中未提及该内容",
            "手术名称": "文本中未提及该内容",
            "术前诊断": "文本中未提及该内容",
            "术中诊断": "文本中未提及该内容",
            "术后诊断": "文本中未提及该内容",
            "病灶描述": "文本中未提及该内容",
            "手术经过": "文本中未提及该内容",
            "术中情况": "文本中未提及该内容",
            "术中出血": "文本中未提及该内容"
        }

        if not records:
            print("没有找到手术记录详情数据")
            return default_result

        # 提取记录内容和时间
        record_creation_time = "xxx"
        record_content = ""

        for record in records:
            # 检查INVLD_FLG
            if 'INVLD_FLG' in record and record['INVLD_FLG'] == 1:
                print("手术记录INVLD_FLG=1，丢弃该记录")
                continue

            # 提取记录创建时间 from DB record
            # Try RCD_DT first, then OPRT_DT
            if "RCD_DT" in record and record["RCD_DT"]:
                 record_creation_time = self.converter.format_date(record["RCD_DT"])
            elif "OPRT_DT" in record and record["OPRT_DT"]: # Fallback
                 record_creation_time = self.converter.format_date(record["OPRT_DT"])


            # 输出所有可用字段，帮助诊断问题
            print(f"手术记录详情字段: {list(record.keys())}")

            # 尝试不同可能的字段名称 for content
            content_field_names = ["OPRT_RCD_DCMT_CTT", "DCMT_CTT", "OPRT_PRCS_DSCPT"]

            for field_name in content_field_names:
                if field_name in record and record[field_name]:
                    record_content = record[field_name]
                    print(f"成功从字段 {field_name} 提取手术记录内容，长度: {len(record_content)}")
                    break

            if record_content:
                break

        if not record_content:
            print("未找到手术记录内容，检查是否缺少相关字段")
            default_result["创建时间"] = record_creation_time
            return default_result

        # Use LLM to extract information including "手术日期"
        prompt = f"""
    请根据以下手术记录文本，提取关键信息：

    {record_content}

    请从文本中提取以下字段信息：
    - 手术日期（手术的开始时间和结束时间）
    - 手术名称（实施的手术名称）
    - 术前诊断（手术前的诊断结果）
    - 术中诊断（手术中的诊断结果）
    - 术后诊断（手术后的诊断结果）
    - 病灶描述（对病灶的具体描述）
    - 手术经过（手术的详细过程）
    - 术中情况（手术过程中的特殊情况）
    - 术中出血（手术中的出血量）

    你必须严格按照以下格式返回JSON，不要添加任何其他说明或解释：
    {{
      "手术日期": "提取到的手术日期或'文本中未提及该内容'",
      "手术名称": "提取到的手术名称或'文本中未提及该内容'",
      "术前诊断": "提取到的术前诊断或'文本中未提及该内容'",
      "术中诊断": "提取到的术中诊断或'文本中未提及该内容'",
      "术后诊断": "提取到的术后诊断或'文本中未提及该内容'",
      "病灶描述": "提取到的病灶描述或'文本中未提及该内容'",
      "手术经过": "提取到的手术经过或'文本中未提及该内容'",
      "术中情况": "提取到的术中情况或'文本中未提及该内容'",
      "术中出血": "提取到的术中出血量或'文本中未提及该内容'"
    }}

    重要提示：
    1. 必须严格按照JSON格式返回，不要添加任何额外的文字
    2. 所有字段值必须用双引号包围
    3. 如果文本中未提及某个字段的内容，该字段值必须为"文本中未提及该内容"
    4. 仔细寻找文档中的日期时间信息，特别是"手术开始时间"、"手术结束时间"等
    5. 确保JSON格式完全正确，每个字段后都要有逗号（最后一个字段除外）

    特别注意：1、仔细寻找文档中的任何日期时间信息。
    2、如果文本中未提及某个字段的内容，则该字段的值应为"文本中未提及该内容"。
    3、文本中若有与诊疗无关的个人敏感信息（包括：姓名，电话，邮箱，身份证号，地址等），将其隐藏为***，如文本“现住浙江省杭州市/生于浙江省杭州市”包含地址信息，将其隐藏为“现住***/生于***”，不要隐去性别、年龄等和诊疗有关的关键个人信息。
        """

        print("调用大模型提取手术记录信息...")
        response = chat_method(prompt)
        print(f"大模型响应长度: {len(response)}")

        try:
            # Find JSON range
            json_start = response.find("{")
            json_end = response.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                # Extract JSON part
                json_str = response[json_start:json_end]
                print(f"提取到JSON字符串，长度: {len(json_str)}")

                # Clean and format JSON string
                json_str = json_str.replace("'", '"').replace('\n', ' ')

                try:
                    # Parse JSON
                    extracted_data = json.loads(json_str)
                    print("成功解析手术记录JSON")

                    # Build result dictionary with correct field names
                    result = default_result.copy()

                    # Set creation time from DB record
                    result["创建时间"] = record_creation_time

                    # Set surgical time from LLM extracted "手术日期"
                    result["手术时间"] = extracted_data.get("手术日期", "文本中未提及该内容")

                    # Copy other extracted fields
                    for key, value in extracted_data.items():
                         if key != "手术日期" and key in result: # Only copy if the key is in our default_result (excluding "手术日期")
                             result[key] = value


                    return result

                except json.JSONDecodeError as e:
                    print(f"手术记录JSON解析失败: {e}")
                    print(f"问题JSON字符串: {json_str}")
                    
                    # 使用专门的JSON修复函数
                    fixed_json = self._fix_operation_json(json_str)
                    if fixed_json:
                        try:
                            extracted_data = json.loads(fixed_json)
                            print("使用修复函数成功解析手术记录JSON")
                            
                            # Build result dictionary from fixed data
                            result = default_result.copy()
                            result["创建时间"] = record_creation_time
                            result["手术时间"] = extracted_data.get("手术日期", "文本中未提及该内容")
                            for key, value in extracted_data.items():
                                 if key != "手术日期" and key in result:
                                     result[key] = value
                            return result
                        except Exception as e2:
                            print(f"修复后的JSON仍然解析失败: {e2}")
                    
                    # 最后的备用方案：手动解析关键信息
                    print("尝试手动解析手术记录关键信息...")
                    try:
                        manual_result = default_result.copy()
                        manual_result["创建时间"] = record_creation_time
                        
                        # 从原始文本中手动提取一些关键信息
                        content_lower = record_content.lower()
                        
                        # 提取手术名称
                        if "手术名称" in record_content:
                            surgery_name_match = re.search(r'手术名称[：:]\s*([^\n\r]+)', record_content)
                            if surgery_name_match:
                                manual_result["手术名称"] = surgery_name_match.group(1).strip()
                        
                        # 提取手术日期
                        date_patterns = [
                            r'手术开始时间[：:]\s*(\d{4}年\d{1,2}月\d{1,2}日)',
                            r'手术结束时间[：:]\s*(\d{4}年\d{1,2}月\d{1,2}日)',
                            r'(\d{4}年\d{1,2}月\d{1,2}日)'
                        ]
                        for pattern in date_patterns:
                            date_match = re.search(pattern, record_content)
                            if date_match:
                                manual_result["手术日期"] = date_match.group(1)
                                break
                        
                        # 提取术前诊断
                        if "手术前诊断" in record_content:
                            pre_diag_match = re.search(r'手术前诊断[：:]\s*([^\n\r]+)', record_content)
                            if pre_diag_match:
                                manual_result["术前诊断"] = pre_diag_match.group(1).strip()
                        
                        # 提取术后诊断
                        if "手术后诊断" in record_content:
                            post_diag_match = re.search(r'手术后诊断[：:]\s*([^\n\r]+)', record_content)
                            if post_diag_match:
                                manual_result["术后诊断"] = post_diag_match.group(1).strip()
                        
                        # 提取出血量
                        blood_loss_match = re.search(r'出血量[：:]\s*(\d+)\s*ml', record_content)
                        if blood_loss_match:
                            manual_result["术中出血"] = f"{blood_loss_match.group(1)}ml"
                        
                        # 提取手术经过（简化版本）
                        if "手术经过" in record_content:
                            # 尝试提取手术经过的主要内容
                            surgery_process_match = re.search(r'手术经过[：:]\s*(.*?)(?=\n\n|\n[A-Z]|$)', record_content, re.DOTALL)
                            if surgery_process_match:
                                process_text = surgery_process_match.group(1).strip()
                                # 限制长度，避免过长
                                if len(process_text) > 500:
                                    process_text = process_text[:500] + "..."
                                manual_result["手术经过"] = process_text
                        
                        print("手动解析完成，返回部分提取的结果")
                        return manual_result
                        
                    except Exception as e3:
                        print(f"手动解析也失败: {e3}")
                        return default_result
            else:
                print("未在响应中找到JSON结构")
        except Exception as e:
            print(f"处理手术记录大模型响应时出错: {e}")

        # If all attempts fail, return default result with creation time
        default_result["创建时间"] = record_creation_time
        return default_result

    def process_operation_record(self):
        """处理手术记录，结合结构化字段和大模型提取内容"""
        # 获取结构化字段信息（住院流水号和费用相关）
        structured_records = self.execute_query("手术记录")
        print(f"查询到 {len(structured_records)} 条手术记录结构化数据")
        structured_result = []

        if structured_records:
            for row in structured_records:
                record = {
                    "住院流水号": self.converter.format_value(row.get("O_INHOS_NO", "")),
                    "费用相关": "xxx"  # 默认值
                }

                # 处理费用相关字段
                fee_fields = ["TRTMT_TP_OPRT_TRTMT_FEE", "TRTMT_TP_OPRT_FEE_ATHS_FEE", "TRTMT_TP_OPRT_FEE_OPRT_FEE"]
                fee_units = ["元", "元", "元"]
                fee_prefixes = ["治疗类-手术治疗费", "治疗类-手术治疗费-麻醉费", "治疗类-手术治疗费-手术费"]

                record["费用相关"] = self.converter.concat_fields_with_units(row, fee_fields, fee_units,
                                                                             prefixes=fee_prefixes)

                structured_result.append(record)

        # 获取详细手术记录并使用大模型提取
        detailed_records = self.execute_query("手术记录详情")
        print(f"查询到 {len(detailed_records)} 条手术记录详情数据")

        # 如果有详情数据，打印第一条记录的字段名称以便诊断
        if detailed_records:
            print(f"手术记录详情字段列表: {list(detailed_records[0].keys())}")

        extracted_data = self.extract_operation_record(detailed_records)

        # 合并结果
        final_result = []
        if structured_result:
            for record in structured_result:
                # 合并结构化字段和提取的内容
                merged_record = record.copy()
                for key, value in extracted_data.items():
                    if key not in merged_record:
                        merged_record[key] = value
                # 修正：将此行移到内部循环外，确保每条记录只添加一次
                final_result.append(merged_record)  # 这里的缩进是正确的，在循环外
        else:
            # 如果没有结构化数据，创建一个包含默认住院号和提取内容的记录
            merged_record = {"住院流水号": self.inhos_no, "费用相关": "xxx"}
            for key, value in extracted_data.items():
                merged_record[key] = value
            final_result.append(merged_record)

        return final_result
    def extract_daily_course_records(self, records):
        """
        使用大模型提取多条日常病程记录内容

        Args:
            records: 从数据库查询到的日常病程记录列表

        Returns:
            列表，每个元素是包含时间和文本的字典
        """
        if not records:
            return [{"时间": "xxx", "文本": "xxx"}]  # 返回默认值

        results = []

        for record in records:
            # 检查INVLD_FLG
            if 'INVLD_FLG' in record and record['INVLD_FLG'] == 1:
                print("日常病程记录INVLD_FLG=1，丢弃该记录")
                continue

            # 跳过没有内容的记录
            if "DCMT_CTT" not in record or not record["DCMT_CTT"]:
                continue

            # 提取记录时间和内容
            record_time = "xxx"
            dcmt_content = record["DCMT_CTT"]

            # 从数据库记录中获取基础时间 - 优先使用CRT_TM，然后RCD_DT
            if "CRT_TM" in record and record["CRT_TM"]:
                record_time = self.converter.format_date(record["CRT_TM"])
                print(f"日常病程记录使用CRT_TM作为创建时间: {record_time}")
            elif "RCD_DT" in record and record["RCD_DT"]:
                record_time = self.converter.format_date(record["RCD_DT"])
                print(f"日常病程记录使用RCD_DT作为创建时间: {record_time}")

            # 如果内容太短，直接使用内容作为文本
            if len(dcmt_content) < 100:
                results.append({
                    "时间": record_time,
                    "文本": dcmt_content
                })
                continue
            print(f"处理日常病程记录，内容长度: {len(dcmt_content)}")

            # 使用大模型提取信息
            prompt = f"""
    请从以下日常病程记录中提取关键信息：

    {dcmt_content}

    请提取以下字段信息：
    - 文档记录时间（文档中显示的时间，通常在文档开头，格式为年-月-日或年-月-日 时:分等）
    - 文本内容（病程记录的主要内容）

    你必须严格按照以下格式返回JSON：
    {{
      "文档记录时间": "提取到的时间或'文本中未提及该内容'",
      "文本内容": "病程记录的核心内容摘要"
    }}

    特别注意：1、仔细寻找文档中的任何日期时间信息，特别是文档开头部分的时间戳。日常病程记录的时间通常会显示在文档顶部。
    2、文本中若有与诊疗无关的个人敏感信息（包括：姓名，电话，邮箱，身份证号，地址等），将其隐藏为***，如文本“现住浙江省杭州市/生于浙江省杭州市”包含地址信息，将其隐藏为“现住***/生于***”，不要隐去性别、年龄等和诊疗有关的关键个人信息。
    """

            print(f"调用大模型提取日常病程记录信息...")
            response = multi_model_api.chat_method_for_module("日常病程记录", prompt)
            print(f"大模型响应长度: {len(response)}")

            # 尝试解析JSON
            try:
                # 找出JSON的范围
                json_start = response.find("{")
                json_end = response.rfind("}") + 1

                if json_start >= 0 and json_end > json_start:
                    # 提取JSON部分
                    json_str = response[json_start:json_end]
                    print(f"提取到JSON字符串，长度: {len(json_str)}")

                    # 清理和格式化JSON字符串
                    json_str = json_str.replace("'", '"')  # 单引号替换为双引号
                    json_str = json_str.replace('\n', ' ')  # 移除换行符

                    try:
                        # 解析JSON
                        extracted_data = json.loads(json_str)
                        print("成功解析日常病程记录JSON")

                        # 从提取的数据中获取时间，如果没有则使用数据库记录时间
                        doc_time = extracted_data.get("文档记录时间", "文本中未提及该内容")
                        if doc_time and doc_time != "文本中未提及该内容":
                            record_time = doc_time

                        # 获取文本内容
                        text_content = extracted_data.get("文本内容", "文本中未提及该内容")

                        # 添加到结果列表
                        results.append({
                            "时间": record_time,
                            "文本": text_content
                        })
                    except json.JSONDecodeError as e:
                        print(f"日常病程记录JSON解析失败: {e}")

                        # 尝试修复JSON格式
                        try:
                            # 确保键使用双引号
                            json_str = re.sub(r'([{,])\s*([a-zA-Z0-9_\u4e00-\u9fa5]+)\s*:', r'\1"\2":', json_str)
                            # 确保值使用双引号（如果不是数字）
                            json_str = re.sub(r':\s*([^",\{\}\[\]\d][^",\{\}\[\]]*[^",\{\}\[\]\d])\s*([,\}])',
                                              r':"\1"\2',
                                              json_str)

                            # 再次尝试解析
                            extracted_data = json.loads(json_str)
                            print("修复后成功解析日常病程记录JSON")

                            # 从提取的数据中获取时间，如果没有则使用数据库记录时间
                            doc_time = extracted_data.get("文档记录时间", "文本中未提及该内容")
                            if doc_time and doc_time != "文本中未提及该内容":
                                record_time = doc_time

                            # 获取文本内容
                            text_content = extracted_data.get("文本内容", "文本中未提及该内容")

                            # 添加到结果列表
                            results.append({
                                "时间": record_time,
                                "文本": text_content
                            })
                        except Exception as e2:
                            print(f"修复日常病程记录JSON后仍然解析失败: {e2}")
                            # 如果解析失败，仍添加一个基本记录
                            results.append({
                                "时间": record_time,
                                "文本": dcmt_content[:300] + "..." if len(dcmt_content) > 300 else dcmt_content
                            })
                else:
                    print("未在日常病程记录响应中找到JSON结构")
                    # 添加一个基本记录
                    results.append({
                        "时间": record_time,
                        "文本": dcmt_content[:300] + "..." if len(dcmt_content) > 300 else dcmt_content
                    })
            except Exception as e:
                print(f"处理日常病程记录大模型响应时出错: {e}")
                # 添加一个基本记录
                results.append({
                    "时间": record_time,
                    "文本": dcmt_content[:300] + "..." if len(dcmt_content) > 300 else dcmt_content
                })

        # 如果没有成功提取任何记录，返回默认值
        if not results:
            return [{"时间": "xxx", "文本": "xxx"}]

        # 按时间排序
        from datetime import datetime

        def parse_date_safe(date_str):
            if not date_str or date_str == "xxx" or date_str == "文本中未提及该内容":
                return datetime.max
            try:
                for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y年%m月%d日 %H:%M", "%Y年%m月%d日"]:
                    try:
                        return datetime.strptime(date_str, fmt)
                    except ValueError:
                        continue
                return datetime.max
            except:
                return datetime.max

        # 排序结果（按时间升序）
        results.sort(key=lambda x: parse_date_safe(x["时间"]))

        return results

    def extract_chemotherapy_records(self, records):
        """
        使用大模型提取多条化疗记录内容

        Args:
            records: 从数据库查询到的化疗记录列表

        Returns:
            列表，每个元素是包含化疗记录信息的字典
        """
        results = []
        
        if not records:
            print("未找到化疗记录")
            return results

        print(f"找到 {len(records)} 条化疗记录")

        for record in records:
            # 检查INVLD_FLG
            if 'INVLD_FLG' in record and record['INVLD_FLG'] == 1:
                print("化疗记录INVLD_FLG=1，丢弃该记录")
                continue

            # 跳过没有内容的记录
            dcmt_content = record.get("DCMT_CTT", "")
            if not dcmt_content or dcmt_content.strip() == "":
                print("化疗记录内容为空，跳过")
                continue

            # 从数据库记录中获取基础时间 - 优先使用CRT_TM，然后RCD_DT
            if "CRT_TM" in record and record["CRT_TM"]:
                record_time = self.converter.format_date(record["CRT_TM"])
                print(f"化疗记录使用CRT_TM作为创建时间: {record_time}")
            elif "RCD_DT" in record and record["RCD_DT"]:
                record_time = self.converter.format_date(record["RCD_DT"])
                print(f"化疗记录使用RCD_DT作为创建时间: {record_time}")
            else:
                record_time = "xxx"

            # 如果内容太短，直接使用内容作为文本
            if len(dcmt_content) < 100:
                results.append({
                    "时间": record_time,
                    "化疗药品名称": dcmt_content[:50] + "..." if len(dcmt_content) > 50 else dcmt_content,
                    "药品剂量": "文本中未提及该内容",
                    "化疗方案": "文本中未提及该内容",
                    "化疗周期": "文本中未提及该内容",
                    "化疗日期": "文本中未提及该内容",
                    "化疗反应": "文本中未提及该内容",
                    "化疗效果": "文本中未提及该内容",
                    "备注": "文本中未提及该内容"
                })
                continue
            print(f"处理化疗记录，内容长度: {len(dcmt_content)}")

            # 使用大模型提取信息
            prompt = f"""
    请从以下化疗记录中提取关键信息：

    {dcmt_content}

    请提取以下字段信息：
    - 文档记录时间（文档中显示的时间，通常在文档开头，格式为年-月-日或年-月-日 时:分等）
    - 化疗药品名称（使用的化疗药物名称）
    - 药品剂量（药物的使用剂量）
    - 化疗方案（采用的化疗方案名称）
    - 化疗周期（第几个化疗周期）
    - 化疗日期（具体的化疗日期）
    - 化疗反应（患者对化疗的反应情况）
    - 化疗效果（化疗的治疗效果）
    - 备注（其他重要信息）

    你必须严格按照以下格式返回JSON：
    {{
      "文档记录时间": "提取到的时间或'文本中未提及该内容'",
      "化疗药品名称": "药品名称或'文本中未提及该内容'",
      "药品剂量": "剂量信息或'文本中未提及该内容'",
      "化疗方案": "方案名称或'文本中未提及该内容'",
      "化疗周期": "周期信息或'文本中未提及该内容'",
      "化疗日期": "化疗日期或'文本中未提及该内容'",
      "化疗反应": "反应情况或'文本中未提及该内容'",
      "化疗效果": "治疗效果或'文本中未提及该内容'",
      "备注": "其他信息或'文本中未提及该内容'"
    }}

    特别注意：1、仔细寻找文档中的任何日期时间信息，特别是文档开头部分的时间戳。化疗记录的时间通常会显示在文档顶部。
    2、文本中若有与诊疗无关的个人敏感信息（包括：姓名，电话，邮箱，身份证号，地址等），将其隐藏为***，如文本"现住浙江省杭州市/生于浙江省杭州市"包含地址信息，将其隐藏为"现住***/生于***"，不要隐去性别、年龄等和诊疗有关的关键个人信息。
    """

            print(f"调用大模型提取化疗记录信息...")
            response = multi_model_api.chat_method_for_module("化疗记录", prompt)
            print(f"大模型响应长度: {len(response)}")

            # 尝试解析JSON
            try:
                # 找出JSON的范围
                json_start = response.find("{")
                json_end = response.rfind("}") + 1

                if json_start != -1 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    print(f"提取的JSON字符串: {json_str[:200]}...")

                    try:
                        # 解析JSON
                        extracted_data = json.loads(json_str)
                        print("成功解析化疗记录JSON")

                        # 从提取的数据中获取时间，如果没有则使用数据库记录时间
                        doc_time = extracted_data.get("文档记录时间", "文本中未提及该内容")
                        if doc_time == "文本中未提及该内容" or doc_time == "xxx":
                            doc_time = record_time

                        # 构建结果
                        results.append({
                            "时间": doc_time,
                            "化疗药品名称": extracted_data.get("化疗药品名称", "文本中未提及该内容"),
                            "药品剂量": extracted_data.get("药品剂量", "文本中未提及该内容"),
                            "化疗方案": extracted_data.get("化疗方案", "文本中未提及该内容"),
                            "化疗周期": extracted_data.get("化疗周期", "文本中未提及该内容"),
                            "化疗日期": extracted_data.get("化疗日期", "文本中未提及该内容"),
                            "化疗反应": extracted_data.get("化疗反应", "文本中未提及该内容"),
                            "化疗效果": extracted_data.get("化疗效果", "文本中未提及该内容"),
                            "备注": extracted_data.get("备注", "文本中未提及该内容")
                        })
                    except json.JSONDecodeError as e:
                        print(f"化疗记录JSON解析失败: {e}")

                        # 尝试修复JSON格式
                        try:
                            # 简单的JSON修复
                            json_str = json_str.replace("'", '"')
                            json_str = re.sub(r'(\w+):', r'"\1":', json_str)

                            # 再次尝试解析
                            extracted_data = json.loads(json_str)
                            print("修复后成功解析化疗记录JSON")

                            # 从提取的数据中获取时间，如果没有则使用数据库记录时间
                            doc_time = extracted_data.get("文档记录时间", "文本中未提及该内容")
                            if doc_time == "文本中未提及该内容" or doc_time == "xxx":
                                doc_time = record_time

                            # 构建结果
                            results.append({
                                "时间": doc_time,
                                "化疗药品名称": extracted_data.get("化疗药品名称", "文本中未提及该内容"),
                                "药品剂量": extracted_data.get("药品剂量", "文本中未提及该内容"),
                                "化疗方案": extracted_data.get("化疗方案", "文本中未提及该内容"),
                                "化疗周期": extracted_data.get("化疗周期", "文本中未提及该内容"),
                                "化疗日期": extracted_data.get("化疗日期", "文本中未提及该内容"),
                                "化疗反应": extracted_data.get("化疗反应", "文本中未提及该内容"),
                                "化疗效果": extracted_data.get("化疗效果", "文本中未提及该内容"),
                                "备注": extracted_data.get("备注", "文本中未提及该内容")
                            })
                        except Exception as e2:
                            print(f"修复化疗记录JSON后仍然解析失败: {e2}")
                            # 如果解析失败，仍添加一个基本记录
                            results.append({
                                "时间": record_time,
                                "化疗药品名称": dcmt_content[:100] + "..." if len(dcmt_content) > 100 else dcmt_content,
                                "药品剂量": "文本中未提及该内容",
                                "化疗方案": "文本中未提及该内容",
                                "化疗周期": "文本中未提及该内容",
                                "化疗日期": "文本中未提及该内容",
                                "化疗反应": "文本中未提及该内容",
                                "化疗效果": "文本中未提及该内容",
                                "备注": "文本中未提及该内容"
                            })
                else:
                    print("未在化疗记录响应中找到JSON结构")
                    # 添加一个基本记录
                    results.append({
                        "时间": record_time,
                        "化疗药品名称": dcmt_content[:100] + "..." if len(dcmt_content) > 100 else dcmt_content,
                        "药品剂量": "文本中未提及该内容",
                        "化疗方案": "文本中未提及该内容",
                        "化疗周期": "文本中未提及该内容",
                        "化疗日期": "文本中未提及该内容",
                        "化疗反应": "文本中未提及该内容",
                        "化疗效果": "文本中未提及该内容",
                        "备注": "文本中未提及该内容"
                    })
            except Exception as e:
                print(f"处理化疗记录大模型响应时出错: {e}")
                # 添加一个基本记录
                results.append({
                    "时间": record_time,
                    "化疗药品名称": dcmt_content[:100] + "..." if len(dcmt_content) > 100 else dcmt_content,
                    "药品剂量": "文本中未提及该内容",
                    "化疗方案": "文本中未提及该内容",
                    "化疗周期": "文本中未提及该内容",
                    "化疗日期": "文本中未提及该内容",
                    "化疗反应": "文本中未提及该内容",
                    "化疗效果": "文本中未提及该内容",
                    "备注": "文本中未提及该内容"
                })

        # 按时间排序
        def parse_date_safe(date_str):
            """安全解析日期字符串"""
            if not date_str or date_str == "xxx" or date_str == "文本中未提及该内容":
                return datetime.min
            try:
                # 尝试多种日期格式
                formats = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日"]
                for fmt in formats:
                    try:
                        return datetime.strptime(date_str, fmt)
                    except ValueError:
                        continue
                return datetime.max
            except:
                return datetime.max

        # 排序结果（按时间升序）
        results.sort(key=lambda x: parse_date_safe(x["时间"]))

        return results

    def extract_multiple_records(self, records_dict):
        """
        批量提取多个文档的内容，减少对大模型的调用次数

        Args:
            records_dict: 包含各类文档内容的字典，格式为 {文档类型: 文档内容}

        Returns:
            包含提取结果的字典
        """
        if not records_dict or all(not content for content in records_dict.values()):
            return {}

        # 构建批量提取的提示词
        prompt = """请从以下多个医疗文档中提取相关信息，严格按照要求返回JSON格式：\n\n"""

        # 添加各文档内容及提取要求
        if "入院记录" in records_dict and records_dict["入院记录"]:
            prompt += f"""## 入院记录文档
    {records_dict["入院记录"]}

    入院记录需提取字段:
    - 文档记录时间（文档中显示的时间）
    - 患者一般情况
    - 主诉
    - 现病史
    - 既往史
    - 个人史
    - 婚育史
    - 月经史
    - 家族史
    - 体格检查
    - 专科情况
    - 辅助检查
    - 初步诊断
    - 更正诊断
    - FIGO分期
    - TNM分期
    - 其他肿瘤分期
    - 主治医师48小时诊断

    """

        if "首次病程记录" in records_dict and records_dict["首次病程记录"]:
            prompt += f"""## 首次病程记录文档
    {records_dict["首次病程记录"]}

    首次病程记录需提取字段:
    - 文档记录时间（文档中显示的时间）
    - 病例特点
    - 初步诊断
    - 诊断依据
    - 鉴别诊断
    - 诊疗计划

    """

        if "出院记录" in records_dict and records_dict["出院记录"]:
            prompt += f"""## 出院记录文档
    {records_dict["出院记录"]}

    出院记录需提取字段:
    - 文档记录时间（文档中显示的时间）
    - 入院日期
    - 出院日期
    - 入院诊断
    - 出院诊断
    - 入院情况
    - 诊疗经过
    - 合并症
    - 出院情况
    - 出院医嘱

    """

        if "主治医师查房" in records_dict and records_dict["主治医师查房"]:
            prompt += f"""## 主治医师查房记录文档
    {records_dict["主治医师查房"]}

    主治医师查房记录需提取字段:
    - 文档记录时间（文档中显示的时间）
    - 主治医生查房
    - 诊断
    - 诊断依据
    - 鉴别诊断
    - 诊疗计划
    - 补充病史和体征

    """

        if "主任医师查房" in records_dict and records_dict["主任医师查房"]:
            prompt += f"""## 主任医师查房记录文档
    {records_dict["主任医师查房"]}

    主任医师查房记录需提取字段:
    - 文档记录时间（文档中显示的时间）
    - 主任医生查房
    - 诊疗计划
    - 注意事项
    - 补充病史与体征
    - 对病情的分析
    - 诊疗意见

    """

        if "手术记录" in records_dict and records_dict["手术记录"]:
            prompt += f"""## 手术记录文档
    {records_dict["手术记录"]}

    手术记录需提取字段:
    - 手术时间
    - 手术名称
    - 术前诊断
    - 术中诊断
    - 术后诊断
    - 病灶描述
    - 手术经过
    - 术中情况
    - 术中出血

    """

        # 添加最终输出格式要求
        prompt += """
    请以严格的JSON格式返回提取结果，结构如下：
    {
      "入院记录": {
        "文档记录时间": "...",
        "患者一般情况": "...",
        ...
      },
      "首次病程记录": {
        "文档记录时间": "...",
        "病例特点": "...",
        "初步诊断": "...",
        "诊断依据": "...",
        "鉴别诊断": "...",
        "诊疗计划": "..."
      },
      ...以此类推
    }

    对于文档中未提及的内容，对应字段值填写"文本中未提及该内容"。不要添加任何额外的解释性文字，只返回JSON格式的结果。
    文本中若有与诊疗无关的个人敏感信息（包括：姓名，电话，邮箱，身份证号，地址等），将其隐藏为***，如文本“现住浙江省杭州市/生于浙江省杭州市”包含地址信息，将其隐藏为“现住***/生于***”，不要隐去性别、年龄等和诊疗有关的关键个人信息。
    """

        print("批量调用大模型提取多个文档信息...")
        # 这里暂时保持单模型处理，因为涉及多个文档的综合分析
        response = chat_method(prompt)
        print(f"大模型批量响应长度: {len(response)}")

        # 尝试解析JSON
        try:
            # 找出JSON的范围
            json_start = response.find("{")
            json_end = response.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                # 提取JSON部分
                json_str = response[json_start:json_end]
                print(f"提取到JSON字符串，长度: {len(json_str)}")

                # 清理和格式化JSON字符串
                json_str = json_str.replace("'", '"')  # 单引号替换为双引号
                json_str = json_str.replace('\n', ' ')  # 移除换行符

                try:
                    # 解析JSON
                    extracted_data = json.loads(json_str)
                    print("成功解析批量提取的JSON数据")
                    return extracted_data
                except json.JSONDecodeError as e:
                    print(f"JSON解析失败: {e}")

                    # 尝试修复JSON格式
                    try:
                        # 确保键使用双引号
                        json_str = re.sub(r'([{,])\s*([a-zA-Z0-9_\u4e00-\u9fa5]+)\s*:', r'\1"\2":', json_str)
                        # 确保值使用双引号（如果不是数字）
                        json_str = re.sub(r':\s*([^",\{\}\[\]\d][^",\{\}\[\]]*[^",\{\}\[\]\d])\s*([,\}])', r':"\1"\2',
                                          json_str)

                        # 再次尝试解析
                        extracted_data = json.loads(json_str)
                        print("修复后成功解析批量提取的JSON数据")
                        return extracted_data
                    except Exception as e2:
                        print(f"修复JSON后仍然解析失败: {e2}")
            else:
                print("未在响应中找到JSON结构")
        except Exception as e:
            print(f"处理批量提取大模型响应时出错: {e}")

        # 如果所有尝试都失败，返回空字典
        return {}

    def process_documents_parallel_wrapper(self, document_tasks):
        """包装器方法，调用全局多模型API的并行处理功能"""
        return multi_model_api.process_documents_parallel(document_tasks)
    
    def process_operation_record_wrapper(self, operation_records):
        """手术记录处理包装器，用于并行处理"""
        if not operation_records:
            return {}
        return self.process_operation_record()
    
    def process_all_and_export(self, output_file=None, existing_icd10=None):
        # 定义应包含的所有模块
        required_modules = ["病理", "医嘱", "护理记录", "检查", "检验", "诊断", "手术记录", "收费", "医保", "治疗用药", "手术用药"]
        required_documents = ["入院记录", "首次病程记录", "主治医师首次查房记录", "主任医师首次查房记录", "日常病程记录", "化疗记录", "出院记录"]
        empty_modules = []
        result = {"病历文书": [], "主要ICD10编码": {}}
        print("获取所有需要AI处理的文档原始数据...")
        admission_records = self.execute_query("入院记录")
        first_course_records = self.execute_query("首次病程记录")
        attending_round_records = self.execute_query("上级医生查房记录")
        chief_round_records = attending_round_records.copy() if attending_round_records else []
        daily_records = self.execute_query("日常病程记录")
        chemotherapy_records = self.execute_query("化疗记录")
        discharge_records = self.execute_query("出院记录")
        operation_records = self.execute_query("手术记录详情")

        # ======================================================
        # 第2.1步：并行处理所有需要AI分析的文档
        # ======================================================
        
        print("开始并行处理所有AI文档...")
        
        # 构建完整的并行任务字典
        all_parallel_tasks = {
            "入院记录": (admission_records, self.extract_admission_record),
            "出院记录": (discharge_records, self.extract_discharge_record),
            "首次病程记录": (first_course_records, self.extract_first_course_record),
            "上级医生查房记录": (attending_round_records, lambda x: self.extract_ward_round_records(x, "主治医师")),
            "主任医师查房记录": (chief_round_records, lambda x: self.extract_ward_round_records(x, "主任医师")),
            "日常病程记录": (daily_records, self.extract_daily_course_records),
            "化疗记录": (chemotherapy_records, self.extract_chemotherapy_records),
            "手术记录": (operation_records, self.process_operation_record_wrapper)
        }
        
        # 执行并行处理
        all_parallel_results = self.process_documents_parallel_wrapper(all_parallel_tasks)
        
        # 检查入院记录的处理结果
        extracted_admission = all_parallel_results.get("入院记录", {})
        if isinstance(extracted_admission, dict) and extracted_admission.get("内容缺失", False):
            reason = extracted_admission.get("原因", "入院记录内容缺失")
            print(f"终止处理: {reason}")
            print("由于入院记录缺失，跳过处理该病例")

            # 返回提前终止的结果，但不生成文件
            early_termination = {
                "提前终止": True,
                "终止原因": reason,
                "缺失模块": ["入院记录"]
            }

            return early_termination

        # 入院记录内容完整，继续处理
        # 优先使用数据库的创建时间，如果没有或为xxx，则使用大模型提取的时间
        db_time = extracted_admission.get("创建时间", "xxx")
        llm_time = extracted_admission.get("时间", "xxx")
        
        if db_time != "xxx":
            record_time = db_time
            print(f"入院记录使用数据库创建时间: {record_time}")
        elif llm_time != "xxx":
            record_time = llm_time
            print(f"入院记录使用大模型提取时间: {record_time}")
        else:
            record_time = "xxx"
            print("入院记录未找到有效创建时间")

        # 添加到结果
        result["入院记录"] = {
       "创建时间": record_time,
       **{k: v for k, v in extracted_admission.items() if k not in ["时间", "创建时间"]}}

        # 提取生命体征信息
        physical_exam = extracted_admission.get("体格检查", "")
        if physical_exam and physical_exam != "文本中未提及该内容":
            # 提取第一行，这里假设第一行包含生命体征信息
            first_line = physical_exam.split('\n')[0] if '\n' in physical_exam else physical_exam

            # 解析生命体征数据
            import re
            try:
                # 提取体温 T
                t_match = re.search(r'T[：:]\s*(\d+\.?\d*)℃?', first_line)
                if t_match:
                    self.extracted_vital_signs["T"] = t_match.group(1)

                # 提取脉搏 P
                p_match = re.search(r'P[：:]\s*(\d+)次?\/分', first_line)
                if p_match:
                    self.extracted_vital_signs["P"] = p_match.group(1)

                # 提取呼吸 R
                r_match = re.search(r'R[：:]\s*(\d+)次?\/分', first_line)
                if r_match:
                    self.extracted_vital_signs["R"] = r_match.group(1)

                # 提取血压 BP
                bp_match = re.search(r'BP[：:]\s*(\d+)[\/](\d+)', first_line)
                if bp_match:
                    self.extracted_vital_signs["BP高"] = bp_match.group(1)
                    self.extracted_vital_signs["BP低"] = bp_match.group(2)
            except Exception as e:
                print(f"提取生命体征时出错: {e}")

        print(f"从入院记录中提取的生命体征: {self.extracted_vital_signs}")

        # ======================================================
        # 第2步：获取诊断信息（其他文档数据已获取）
        # ======================================================
        print("获取诊断信息...")

        # 诊断信息
        diagnosis_records = self.execute_query("诊断")
        diagnosis_list = self.converter.process_result("诊断", diagnosis_records) if diagnosis_records else []
        if not diagnosis_list:
            empty_modules.append("诊断")

        # ======================================================
        # 第3步：处理出院诊断并提取主要ICD10编码（使用并行处理结果）
        # ======================================================
        # 使用已有的ICD10匹配结果或提取出院诊断并匹配
        
        # 获取并行处理的出院记录结果
        discharge_extract = all_parallel_results.get("出院记录", {})
        
        if existing_icd10:
            # 使用已有的ICD10匹配结果
            print("使用已有的ICD10匹配结果，跳过出院诊断提取和ICD10匹配步骤")
            main_icd10 = existing_icd10
        else:
            # 首先处理出院诊断，提取主要ICD10编码
            discharge_diagnosis = discharge_extract.get("出院诊断", "文本中未提及该内容")

            if discharge_diagnosis == "文本中未提及该内容" or not discharge_records:
                empty_modules.append("出院记录")

            # 提取主要ICD10编码
            main_icd10 = self.extract_main_icd10_code(discharge_diagnosis, diagnosis_list)
            print(f"主要ICD10编码: {main_icd10['code']} | {main_icd10['name']} (匹配度: {main_icd10['match_rate']}%)")

        # 存储ICD10编码结果
        result["主要ICD10编码"] = main_icd10

        # ======================================================
        # 第4步：整理并行处理结果
        # ======================================================
        
        print("整理并行处理结果...")
        
        # 首次病程记录
        extracted_first_course = all_parallel_results.get("首次病程记录", {})
        if extracted_first_course:
            # 优先使用数据库的创建时间，如果没有或为xxx，则使用大模型提取的时间
            db_time = extracted_first_course.get("创建时间", "xxx")
            llm_time = extracted_first_course.get("时间", "xxx")
            
            if db_time != "xxx":
                record_time = db_time
                print(f"首次病程记录使用数据库创建时间: {record_time}")
            elif llm_time != "xxx":
                record_time = llm_time
                print(f"首次病程记录使用大模型提取时间: {record_time}")
            else:
                record_time = "xxx"
                print("首次病程记录未找到有效创建时间")

            if all(v == "文本中未提及该内容" for k, v in extracted_first_course.items() if
                   k not in ["时间", "创建时间"]) or not first_course_records:
                empty_modules.append("首次病程记录")

            result["首次病程记录"] = {
                "创建时间": record_time,
                **{k: v for k, v in extracted_first_course.items() if k not in ["时间", "创建时间"]}
            }
        else:
            empty_modules.append("首次病程记录")
            result["首次病程记录"] = {"创建时间": "xxx"}

        # 主治医师首次查房记录
        extracted_attending = all_parallel_results.get("上级医生查房记录", {})
        if extracted_attending:
            record_time = extracted_attending.get("时间", "xxx")

            if extracted_attending.get("主治医生查房", "") == "文本中未提及该内容":
                empty_modules.append("主治医师首次查房记录")

            result["主治医师首次查房记录"] = {
                "创建时间": record_time,
                **{k: v for k, v in extracted_attending.items() if k != "时间"}
            }
        else:
            empty_modules.append("主治医师首次查房记录")
            result["主治医师首次查房记录"] = {"创建时间": "xxx"}

        # 主任医师首次查房记录
        extracted_chief = all_parallel_results.get("主任医师查房记录", {})
        if extracted_chief:
            record_time = extracted_chief.get("时间", "xxx")

            if extracted_chief.get("主任医生查房", "") == "文本中未提及该内容":
                empty_modules.append("主任医师首次查房记录")

            result["主任医师首次查房记录"] = {
                "创建时间": record_time,
                **{k: v for k, v in extracted_chief.items() if k != "时间"}
            }
        else:
            empty_modules.append("主任医师首次查房记录")
            result["主任医师首次查房记录"] = {"创建时间": "xxx"}

        # 日常病程记录
        extracted_daily_records = all_parallel_results.get("日常病程记录", [])
        if not extracted_daily_records or (len(extracted_daily_records) <= 1 and extracted_daily_records[0].get("文本", "") == "xxx"):
            empty_modules.append("日常病程记录")

        result["日常病程记录"] = [
            {"创建时间": rec.get("时间", "xxx"), "文本": rec.get("文本", "xxx")}
            for rec in extracted_daily_records
        ]

        # 化疗记录 - 多条记录处理
        extracted_chemotherapy_records = all_parallel_results.get("化疗记录", [])
        if not extracted_chemotherapy_records or (len(extracted_chemotherapy_records) <= 1 and extracted_chemotherapy_records[0].get("化疗药品名称", "") == "xxx"):
            empty_modules.append("化疗记录")

        result["化疗记录"] = [
            {
                "创建时间": rec.get("时间", "xxx"),
                "化疗药品名称": rec.get("化疗药品名称", "xxx"),
                "药品剂量": rec.get("药品剂量", "xxx"),
                "化疗方案": rec.get("化疗方案", "xxx"),
                "化疗周期": rec.get("化疗周期", "xxx"),
                "化疗日期": rec.get("化疗日期", "xxx"),
                "化疗反应": rec.get("化疗反应", "xxx"),
                "化疗效果": rec.get("化疗效果", "xxx"),
                "备注": rec.get("备注", "xxx")
            }
            for rec in extracted_chemotherapy_records
        ]

        # 处理出院记录（复用之前已提取的结果）
        # 出院记录已经在第3步提取过了，直接使用结果
        # 优先使用数据库的创建时间，如果没有或为xxx，则使用大模型提取的时间
        db_time = discharge_extract.get("创建时间", "xxx")
        llm_time = discharge_extract.get("时间", "xxx")
        
        if db_time != "xxx":
            record_time = db_time
            print(f"出院记录使用数据库创建时间: {record_time}")
        elif llm_time != "xxx":
            record_time = llm_time
            print(f"出院记录使用大模型提取时间: {record_time}")
        else:
            record_time = "xxx"
            print("出院记录未找到有效创建时间")

        result["出院记录"] = {
    "创建时间": record_time,
    **{k: v for k, v in discharge_extract.items() if k not in ["时间", "创建时间"]}
}

        # 手术记录（从并行处理结果中获取）
        operation_result = all_parallel_results.get("手术记录", {})
        if not operation_result or (isinstance(operation_result, list) and len(operation_result) == 1 and all(
                v == "xxx" or v == "文本中未提及该内容" for k, v in operation_result[0].items() if
                k != "住院流水号" and k != "费用相关")):
            empty_modules.append("手术记录")
            result["手术记录"] = []
        else:
            result["手术记录"] = operation_result if isinstance(operation_result, list) else [operation_result]

        # 处理在院评估单（特殊）
        records = self.execute_query("在院评估单")
        result["病历文书"].append({"文书名": "在院评估单", "时间": "xxx", "内容": {}})

        # ======================================================
        # 第5步：处理需要字段映射的模块
        # ======================================================
        print("处理结构化模块数据...")
        modules_to_process = ["病理", "医嘱", "护理记录", "检查", "检验", "诊断信息", "收费", "医保", "用药信息"]
        modules_result = self.process_modules(modules_to_process)

        # 检查哪些结构化模块为空
        for module in modules_to_process:
            if module not in modules_result or not modules_result[module]:
                empty_modules.append(module)

        # 手动添加已处理的诊断信息
        modules_result["诊断"] = diagnosis_list

        # 用药信息模块已经在 modules_result 中处理完成，直接使用

        # 用药信息模块已经通过modules_result统一处理


        processed_insurance_data = []
        # 从已处理的护理记录中获取性别和年龄
        # 假设 nursing_raw_records 仍然可用，或者从 modules_result["护理记录"] 中提取
        # 这里我们假设 nursing_raw_records (通过 self.execute_nursing_query() 获得) 包含性别和年龄

        # 确保护理数据已获取
        if not hasattr(self, 'cached_nursing_raw_records'): # 简单缓存示例
            self.cached_nursing_raw_records = self.execute_nursing_query()

        patient_gender = "xxx"
        patient_age = "xxx"

        if self.cached_nursing_raw_records and isinstance(self.cached_nursing_raw_records, list) and len(self.cached_nursing_raw_records) > 0:
            # 假设第一条护理记录包含所需信息 (M_GDR_NM, M_AGE 可能是您在 execute_nursing_query 中使用的别名)
            # 或者从 modules_result["护理记录"] 的 "内容" -> "基本信息" 或 "病人信息" 中提取
            # 为了简化，我们假设可以直接从 self.cached_nursing_raw_records 获取
            # 您可能需要根据 execute_nursing_query 返回的具体结构来调整这里的键名
            first_nursing_record = self.cached_nursing_raw_records[0]
            patient_gender = self.converter.format_value(first_nursing_record.get("GDR_NM") or first_nursing_record.get("M_GDR_NM"))
            patient_age = self.converter.format_value(first_nursing_record.get("AGE") or first_nursing_record.get("M_AGE"))
            patient_AGE_UNT=self.converter.format_value(first_nursing_record.get("AGE_UNT") or first_nursing_record.get("M_AGE_UNT"))
        elif "护理记录" in modules_result and modules_result["护理记录"]:
            # 尝试从已处理的护理记录的嵌套结构中获取
            try:
                first_processed_nursing = modules_result["护理记录"][0]["内容"]["基本信息"] # 或 "病人信息"
                patient_gender = self.converter.format_value(first_processed_nursing.get("性别"))
                patient_age = self.converter.format_value(first_processed_nursing.get("年龄"))
                patient_AGE_UNT = self.converter.format_value(first_processed_nursing.get("年龄单位"))
            except (IndexError, KeyError, TypeError):
                print("警告: 未能从已处理的护理记录中提取性别和年龄。")


        insurance_records_raw = modules_result.get("医保", []) # 这是通过 process_result 初步处理的

        if insurance_records_raw:
            for ins_record_raw in insurance_records_raw: # FACT_INHOS_FEE_STLMT 可能有多条
                # ins_record_raw 此时应该包含映射后的 "医疗保险类别代码" 和 "医疗保险类别名称"
                final_ins_record = {
                    "医疗保险类别代码": ins_record_raw.get("医疗保险类别代码", "xxx"),
                    "医疗保险类别名称": ins_record_raw.get("医疗保险类别名称", "xxx"),
                    "性别": patient_gender,
                    "年龄": patient_age,
                    "年龄单位": patient_AGE_UNT
                }
                processed_insurance_data.append(final_ins_record)
        else: # 如果没有医保记录，仍然添加一条包含性别和年龄的记录
            processed_insurance_data.append({
                "医疗保险类别代码": "xxx",
                "医疗保险类别名称": "xxx",
                "性别": patient_gender,
                "年龄": patient_age,
                "年龄单位": patient_AGE_UNT
            })
            empty_modules.append("医保")


        # 将处理好的医保信息添加到最终结果中
        # modules_result["医保信息"] = processed_insurance_data # 或者直接用 "医保"
        # ## 结束修改 ##


        # 合并结果，并重命名指定的模块
        rename_map = {
            "病理": "病理报告",
            "检查": "检查报告",
            "检验": "检验报告",
            "收费": "收费报告",
            # ## 修改2: 如果需要，为 "医保" 添加重命名，或者直接使用 ##
        }

        # 将所有模块（包括初步处理的医保）加入到 result
        for module, data in modules_result.items():
            if module in ["医保"]: # 跳过初步处理的医保，后面会用 processed_insurance_data
                continue
            new_module_name = rename_map.get(module, module)
            result[new_module_name] = data

        # 添加最终处理好的医保信息
        result["医保信息"] = processed_insurance_data # 使用新键名

        # 新增：提取基本信息模块
        basic_info = {
            "住院流水号": self.inhos_no,
            "入院日期": "xxx",
            "出院日期": "xxx"
        }

        # 从护理记录数据中提取入院/出院日期
        # execute_nursing_query 已经获取了包含这些信息的数据
        # 我们需要再次获取护理记录的原始数据来提取这些顶级字段
        nursing_raw_records = self.execute_nursing_query() # 重新执行查询以获取原始数据

        if nursing_raw_records:
            # 假设基本信息在第一条记录中
            first_record = nursing_raw_records[0]
            basic_info["入院日期"] = self.converter.format_date(first_record.get("ADMN_DT_TM"))
            basic_info["出院日期"] = self.converter.format_date(first_record.get("DSCG_DT_TM"))
            # 住院流水号已经通过self.inhos_no获取，更可靠

        result["基本信息"] = basic_info

        # 添加缺失模块信息到结果的开头(调整结果字典顺序)
        if empty_modules:
            final_result = {"缺失模块": empty_modules}
            for key, value in result.items():
                final_result[key] = value
            result = final_result

        # 导出JSON
        if output_file:
            try:
                # result 是你最终要导出的字典
                for key in ["缺失模块", "病历文书", "主要ICD10编码"]:
                    result.pop(key, None)  # 如果存在就删除

                # 然后再导出
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"数据已导出到: {output_file}")
            except Exception as e:
                print(f"导出JSON失败: {e}")

        return result


def main():
    """主函数 - 支持从CSV文件或手动输入处理住院号"""
    print("请选择处理方式:")
    print("1. 从CSV文件读取住院号")
    print("2. 手动输入住院号")
    choice_mode = input("请输入选择 (1 或 2): ").strip()

    if choice_mode == '2':
        # --- 手动输入住院号逻辑 ---
        print("\n--- 手动输入住院号处理模式 ---")
        manual_output_dir = os.path.join(FIXED_OUTPUT_DIR, "s")
        try:
            os.makedirs(manual_output_dir, exist_ok=True)
            print(f"手动输入处理结果将保存到: {manual_output_dir}")
        except OSError as e:
            print(f"创建手动输入结果目录 {manual_output_dir} 失败: {e}。程序退出。")
            return

        inhos_nos_input_str = input("请输入一个或多个住院号 (用逗号分隔): ").strip()
        if not inhos_nos_input_str:
            print("未输入任何住院号。程序退出。")
            return

        manual_inhos_nos = [no.strip() for no in inhos_nos_input_str.split(',') if no.strip()]
        if not manual_inhos_nos:
            print("输入的住院号无效。程序退出。")
            return

        print(f"\n将处理以下 {len(manual_inhos_nos)} 个手动输入的住院号:")
        for i, inhos_no_val in enumerate(manual_inhos_nos, 1):
            print(f"{i}. {inhos_no_val}")

        confirm_manual_processing = input("确认处理这些记录吗? (y/n): ").lower()
        if confirm_manual_processing != 'y':
            print("操作已取消，程序结束。")
            return

        successfully_processed_manual = []
        failed_to_process_manual = []

        for idx, current_inhos_no in enumerate(manual_inhos_nos):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            print(f"\n{'-' * 50}")
            print(f"处理手动输入的住院号 ({idx + 1}/{len(manual_inhos_nos)}): {current_inhos_no}")

            processor = None
            try:
                processor = MedicalDataProcessor(inhos_no=current_inhos_no)
                output_file_name = f"patient_{current_inhos_no}_{timestamp}.json"
                current_output_file_path = os.path.join(manual_output_dir, output_file_name)

                # 对于手动输入，我们不进行来自CSV的ICD10范围预检查
                # process_all_and_export 会自行提取和处理ICD10信息
                result_data = processor.process_all_and_export(output_file=current_output_file_path)

                if result_data and not result_data.get("提前终止"): # 检查是否提前终止
                    print(f"数据已为住院号 {current_inhos_no} 保存到: {current_output_file_path}")
                    successfully_processed_manual.append(current_inhos_no)
                    
                    # 删除同住院号的旧文件
                    delete_old_files_for_inhos_no(manual_output_dir, current_inhos_no, current_output_file_path)
                elif result_data and result_data.get("提前终止"):
                    print(f"住院号 {current_inhos_no} 处理提前终止: {result_data.get('终止原因', '未知原因')}")
                    failed_to_process_manual.append(current_inhos_no)
                else: # 其他类型的处理失败
                    print(f"住院号 {current_inhos_no} 处理失败或未生成文件。")
                    failed_to_process_manual.append(current_inhos_no)


            except Exception as e_proc:
                print(f"处理住院号 {current_inhos_no} 时发生严重错误: {e_proc}")
                import traceback
                traceback.print_exc()
                failed_to_process_manual.append(current_inhos_no)
            finally:
                if processor and hasattr(processor, 'connection') and processor.connection:
                    try:
                        processor.connection.close()
                        print(f"住院号 {current_inhos_no} 的数据库连接已关闭。")
                    except Exception as e_close_proc:
                        print(f"关闭住院号 {current_inhos_no} 的数据库连接时出错: {e_close_proc}")
        
        print(f"\n{'-' * 60}")
        print(f"手动输入处理完成汇总:")
        print(f"- 尝试处理的住院号数量: {len(manual_inhos_nos)}")
        print(f"- 成功处理并导出的记录: {len(successfully_processed_manual)} 条")
        if successfully_processed_manual:
            print("  成功处理的住院号:")
            for no in successfully_processed_manual: print(f"    - {no}")
        print(f"- 处理失败或提前终止的记录: {len(failed_to_process_manual)} 条")
        if failed_to_process_manual:
            print("  处理失败/终止的住院号:")
            for no in failed_to_process_manual: print(f"    - {no}")
        
        total_json_files_in_manual_dir = 0
        if os.path.exists(manual_output_dir):
            total_json_files_in_manual_dir = len([f for f in os.listdir(manual_output_dir) if f.startswith('patient_') and f.endswith('.json')])
        print(f"\n当前手动输入结果目录 '{manual_output_dir}' 中共有 {total_json_files_in_manual_dir} 个病历JSON文件。")


    elif choice_mode == '1':
        # --- 从CSV文件读取住院号逻辑 (基本保持不变) ---
        print("\n--- 从CSV文件处理模式 ---")
        source_base_dir = "/home/user/bingli"
        disease_folder_names = []

        if os.path.exists(source_base_dir) and os.path.isdir(source_base_dir):
            for item in os.listdir(source_base_dir):
                item_path = os.path.join(source_base_dir, item)
                if os.path.isdir(item_path):
                    disease_folder_names.append(item)

        if not disease_folder_names:
            # 在CSV模式下，如果初始的疾病文件夹列表为空，则直接提示并退出该模式
            print(f"在源路径 {source_base_dir} 未找到任何疾病文件夹以供CSV处理。程序退出CSV处理模式。")
            # 可以选择在这里调用 main() 重新开始，或者直接退出
            return


        print("\n请选择疾病文件夹 (此名称将用于在 /home/user/sy/ 下创建子文件夹):")
        for i, dir_name in enumerate(disease_folder_names, 1):
            print(f"{i}. {dir_name}")

        selected_disease_name_for_output = ""
        original_csv_dir_path = ""

        try:
            choice_str = input(f"请输入文件夹编号(1-{len(disease_folder_names)}): ")
            if not choice_str.isdigit():
                print("输入无效，必须是数字。程序结束。")
                return
            choice = int(choice_str)
            if not (1 <= choice <= len(disease_folder_names)):
                print("输入无效的编号，程序结束。")
                return

            selected_disease_name_for_output = disease_folder_names[choice - 1]
            original_csv_dir_path = os.path.join(source_base_dir, selected_disease_name_for_output)

        except ValueError:
            print("输入无效，必须输入数字，程序结束。")
            return
        except Exception as e:
            print(f"选择疾病文件夹时发生错误: {e}")
            return

        final_json_output_dir = os.path.join(FIXED_OUTPUT_DIR, selected_disease_name_for_output, "结果")
        try:
            os.makedirs(final_json_output_dir, exist_ok=True)
            print(f"JSON输出目录已设置为: {final_json_output_dir}")
        except OSError as e:
            print(f"创建输出目录 {final_json_output_dir} 失败: {e}。请检查权限或路径。")
            return

        csv_files_in_source_dir = []
        if os.path.exists(original_csv_dir_path) and os.path.isdir(original_csv_dir_path):
            for file_name in os.listdir(original_csv_dir_path):
                if file_name.endswith('.csv'):
                    csv_files_in_source_dir.append(file_name)

        if not csv_files_in_source_dir:
            print(f"在源路径 {original_csv_dir_path} 中未找到任何CSV文件。程序结束。")
            return

        print(f"\n在 {selected_disease_name_for_output} (源路径: {original_csv_dir_path}) 中找到以下CSV文件:")
        for i, csv_name in enumerate(csv_files_in_source_dir, 1):
            print(f"{i}. {csv_name}")

        selected_csv_full_path = ""
        selected_csv_name_only = ""
        try:
            csv_choice_str = input(f"请输入CSV文件编号(1-{len(csv_files_in_source_dir)}): ")
            if not csv_choice_str.isdigit():
                print("输入无效，必须是数字。程序结束。")
                return
            csv_choice = int(csv_choice_str)
            if not (1 <= csv_choice <= len(csv_files_in_source_dir)):
                print("输入无效的编号，程序结束。")
                return

            selected_csv_name_only = csv_files_in_source_dir[csv_choice - 1]
            selected_csv_full_path = os.path.join(original_csv_dir_path, selected_csv_name_only)

        except ValueError:
            print("输入无效，必须输入数字，程序结束。")
            return
        except Exception as e:
            print(f"选择CSV文件时发生错误: {e}")
            return

        try:
            icd10_range = ""
            with open(selected_csv_full_path, 'r', encoding='utf-8-sig') as f:
                icd10_range = f.readline().strip()
                print(f"CSV文件 '{selected_csv_name_only}' 第一行 (ICD10编码范围): {icd10_range}")

            try:
                df = pd.read_csv(selected_csv_full_path, skiprows=1, header=None, names=['INHOS_NO_RAW'], dtype=str, skip_blank_lines=True)
                if 'INHOS_NO_RAW' in df.columns:
                    df.dropna(subset=['INHOS_NO_RAW'], inplace=True)
                    df['INHOS_NO'] = df['INHOS_NO_RAW'].astype(str).str.strip()
                    df = df[df['INHOS_NO'] != '']
                else: # CSV可能只有一行（表头）或为空
                    df = pd.DataFrame(columns=['INHOS_NO'])

            except pd.errors.EmptyDataError:
                print(f"CSV文件 {selected_csv_name_only} (跳过首行后) 为空或格式不正确。")
                df = pd.DataFrame(columns=['INHOS_NO']) # 创建一个空的DataFrame以避免后续错误


            if 'INHOS_NO' not in df.columns or df.empty:
                print(f"CSV文件 {selected_csv_name_only} 未能正确解析出 INHOS_NO 列或数据为空。")
                # 即使为空，也允许继续，以便用户可以手动编辑空的CSV或了解情况
                if df.empty:
                    print("CSV文件内容为空（除表头外）。")


            total_records = len(df)
            print(f"\nCSV文件 '{selected_csv_name_only}' 中共有 {total_records} 条有效住院号记录。")
            if total_records == 0:
                print("CSV文件中没有可处理的住院号。允许继续以进行手动编辑CSV。")
                # 不直接退出，允许后续的手动编辑CSV流程

            process_count_str = input(f"请输入要处理的记录数量(默认为20, 输入 'all' 处理全部, 输入0跳过处理进入CSV编辑): ").strip().lower()

            if process_count_str == '0':
                process_count = 0
                print("选择跳过本轮处理，将直接进入CSV编辑（如果选择）。")
            elif process_count_str == 'all':
                process_count = total_records
            else:
                try:
                    process_count = int(process_count_str or "20")
                except ValueError:
                    print("处理数量输入无效，将使用默认值20。")
                    process_count = 20
            
            final_inhos_to_process = []
            if process_count > 0 and total_records > 0:
                process_count = min(process_count, total_records)
                batch_to_process_df = df.head(process_count)
                inhos_nos_from_csv = batch_to_process_df['INHOS_NO'].tolist()

                processed_inhos_in_output_dir = set()
                if os.path.exists(final_json_output_dir):
                    for file in os.listdir(final_json_output_dir):
                        match = re.search(r'patient_([A-Za-z0-9]+)_\d{8}_\d{6}\.json', file)
                        if match:
                            processed_inhos_in_output_dir.add(match.group(1))
                print(f"已在输出目录 {final_json_output_dir} 发现 {len(processed_inhos_in_output_dir)} 个已处理住院号的JSON文件。")

                
                seen_in_this_batch = set()
                for inhos_no_item in inhos_nos_from_csv:
                    clean_inhos_no = str(inhos_no_item).strip()
                    if clean_inhos_no and clean_inhos_no not in processed_inhos_in_output_dir:
                        if clean_inhos_no not in seen_in_this_batch:
                            final_inhos_to_process.append(clean_inhos_no)
                            seen_in_this_batch.add(clean_inhos_no)
                        else:
                            print(f"住院号 {clean_inhos_no} 在当前批次中重复出现，仅处理一次。")
                    elif clean_inhos_no in processed_inhos_in_output_dir:
                         print(f"住院号 {clean_inhos_no} 已在目标目录处理过，跳过。")
                    elif not clean_inhos_no:
                         print("发现一个空的住院号条目，已跳过。")

                if not final_inhos_to_process:
                    print("所有选中的住院号都已在目标目录处理过或列表为空。")
                else:
                    print(f"\n将处理以下 {len(final_inhos_to_process)} 个新的住院号:")
                    for i, inhos_no_val in enumerate(final_inhos_to_process, 1):
                        print(f"{i}. {inhos_no_val}")

                    confirm_processing = input("确认处理这些记录吗? (y/n): ").lower()
                    if confirm_processing != 'y':
                        print("操作已取消。")
                        final_inhos_to_process = [] # 清空列表，不进行处理
            
            elif process_count == 0: # 用户选择不处理
                 final_inhos_to_process = []
            else: # total_records is 0
                 final_inhos_to_process = []


            matched_records_icd10 = []
            unmatched_records_icd10 = []
            successfully_generated_files = []

            if final_inhos_to_process: # 仅当有待处理记录时才进入循环
                for idx, current_inhos_no in enumerate(final_inhos_to_process):
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    print(f"\n{'-' * 50}")
                    print(f"处理CSV中的住院号 ({idx + 1}/{len(final_inhos_to_process)}): {current_inhos_no}")

                    processor = None
                    try:
                        processor = MedicalDataProcessor(inhos_no=current_inhos_no)
                        discharge_records_for_icd_check = processor.execute_query("出院记录")
                        if not discharge_records_for_icd_check:
                            print(f"住院号 {current_inhos_no}: 未找到出院记录，无法进行ICD10范围检查，跳过处理。")
                            unmatched_records_icd10.append(current_inhos_no)
                            continue

                        discharge_content_for_icd_check = ""
                        for record in discharge_records_for_icd_check:
                            if record.get('DCMT_CTT'):
                                discharge_content_for_icd_check = record['DCMT_CTT']
                                break

                        if not discharge_content_for_icd_check:
                            print(f"住院号 {current_inhos_no}: 出院记录内容为空，无法进行ICD10范围检查，跳过处理。")
                            unmatched_records_icd10.append(current_inhos_no)
                            continue

                        extracted_discharge_diag = processor.extract_discharge_diagnosis_first_item(discharge_content_for_icd_check)
                        # print(f"住院号 {current_inhos_no}: 提取的出院诊断为 '{extracted_discharge_diag}'") # 可以取消注释以调试

                        if extracted_discharge_diag == "文本中未提及该内容":
                            print(f"住院号 {current_inhos_no}: 未能从出院记录中提取有效出院诊断，无法进行ICD10范围检查，跳过处理。")
                            unmatched_records_icd10.append(current_inhos_no)
                            continue

                        diagnosis_list_for_icd_check = processor.converter.process_result("诊断", processor.execute_query("诊断"))
                        if not diagnosis_list_for_icd_check:
                            print(f"住院号 {current_inhos_no}: 未找到诊断列表，无法进行ICD10匹配，跳过处理。")
                            unmatched_records_icd10.append(current_inhos_no)
                            continue

                        main_icd10_info = processor.extract_main_icd10_code(extracted_discharge_diag, diagnosis_list_for_icd_check)
                        # print(f"住院号 {current_inhos_no}: ICD10匹配结果: Code={main_icd10_info['code']}, Name={main_icd10_info['name']}, MatchRate={main_icd10_info['match_rate']}%") # 可以取消注释以调试


                        is_in_icd10_range, matched_range_part = processor.is_icd10_in_range(main_icd10_info['code'], icd10_range)

                        if is_in_icd10_range:
                            print(f"住院号 {current_inhos_no}: 主要ICD10编码 {main_icd10_info['code']} 在目标范围 '{icd10_range}' 内 (匹配部分: {matched_range_part})。")
                            
                            output_file_name = f"patient_{current_inhos_no}_{timestamp}.json"
                            current_output_file_path = os.path.join(final_json_output_dir, output_file_name)
                            
                            result_data = processor.process_all_and_export(output_file=current_output_file_path, existing_icd10=main_icd10_info)
                            if result_data and not result_data.get("提前终止"):
                                print(f"数据已为住院号 {current_inhos_no} 保存到: {current_output_file_path}")
                                successfully_generated_files.append(current_output_file_path)
                                matched_records_icd10.append(current_inhos_no) # 只有成功导出才加入此列表
                                
                                # 删除同住院号的旧文件
                                delete_old_files_for_inhos_no(final_json_output_dir, current_inhos_no, current_output_file_path)
                            elif result_data and result_data.get("提前终止"):
                                print(f"住院号 {current_inhos_no} 处理提前终止: {result_data.get('终止原因', '未知原因')}")
                                unmatched_records_icd10.append(current_inhos_no) # 即使在范围内，但处理终止
                            else:
                                print(f"住院号 {current_inhos_no} 处理失败或未生成文件，即使其ICD10在范围内。")
                                unmatched_records_icd10.append(current_inhos_no)

                        else:
                            print(f"住院号 {current_inhos_no}: 主要ICD10编码 {main_icd10_info['code']} 不在目标范围 '{icd10_range}' 内，跳过完整数据处理和导出。")
                            unmatched_records_icd10.append(current_inhos_no)

                    except Exception as e_proc:
                        print(f"处理住院号 {current_inhos_no} 时发生严重错误: {e_proc}")
                        import traceback
                        traceback.print_exc()
                        if current_inhos_no not in unmatched_records_icd10 and current_inhos_no not in matched_records_icd10:
                            unmatched_records_icd10.append(current_inhos_no)
                    finally:
                        if processor and hasattr(processor, 'connection') and processor.connection:
                            try:
                                processor.connection.close()
                                # print(f"住院号 {current_inhos_no} 的数据库连接已关闭。") # 可以取消注释以调试
                            except Exception as e_close_proc:
                                print(f"关闭住院号 {current_inhos_no} 的数据库连接时出错: {e_close_proc}")
            
# --- CSV处理模式的汇总和CSV更新 ---
            print(f"\n{'-' * 60}")
            print(f"CSV模式处理完成汇总:")
            if final_inhos_to_process: # 检查本轮是否有计划处理的住院号
                 print(f"- 本次计划处理新的住院号数量: {len(final_inhos_to_process)}")
                 print(f"- 符合ICD10范围并成功导出的记录: {len(matched_records_icd10)} 条")
                 if matched_records_icd10:
                     print("  符合条件的住院号:")
                     for inhos_no_val in matched_records_icd10: print(f"    - {inhos_no_val}")

                 print(f"- 因ICD10不符或处理失败/终止而未导出的记录: {len(unmatched_records_icd10)} 条")
                 if unmatched_records_icd10:
                     print("  未导出/不符合ICD10的住院号:")
                     # 确保 unmatched_records_icd10 包含所有未成功导出的 final_inhos_to_process 中的号
                     # (当前逻辑应该已经覆盖了，但可以加一层保险，例如 final_inhos_to_process 中不在 matched_records_icd10 的都算)
                     for inhos_no_val in unmatched_records_icd10: print(f"    - {inhos_no_val}")
            else:
                print("- 本轮未处理任何住院号（可能因为用户选择跳过，或无符合条件的记录）。")


            if successfully_generated_files:
                print(f"\n成功生成的JSON文件 ({len(successfully_generated_files)} 个):")
                for file_p in successfully_generated_files: print(f"  - {file_p}")

            total_json_files_in_output = 0
            if os.path.exists(final_json_output_dir):
                total_json_files_in_output = len([f for f in os.listdir(final_json_output_dir) if f.startswith('patient_') and f.endswith('.json')])
            print(f"\n当前输出子目录 '{selected_disease_name_for_output}/结果/' 中共有 {total_json_files_in_output} 个病历JSON文件。")

            # 自动更新CSV文件：移除本次所有尝试处理过的住院号
            # 修改开始
            if final_inhos_to_process: # 只要本轮有计划处理的住院号，就尝试更新CSV
                print(f"\n准备从CSV文件 '{selected_csv_name_only}' 中移除本轮尝试处理的 {len(final_inhos_to_process)} 条住院号...")
                try:
                    # 重新读取原始CSV文件的所有住院号（跳过第一行表头）
                    df_original_csv_content = pd.read_csv(selected_csv_full_path, skiprows=1, header=None, names=['INHOS_NO_RAW'], dtype=str, skip_blank_lines=True)
                    if 'INHOS_NO_RAW' in df_original_csv_content.columns:
                        df_original_csv_content.dropna(subset=['INHOS_NO_RAW'], inplace=True)
                        df_original_csv_content['INHOS_NO'] = df_original_csv_content['INHOS_NO_RAW'].astype(str).str.strip()
                        df_original_csv_content = df_original_csv_content[df_original_csv_content['INHOS_NO'] != '']
                    else:
                        df_original_csv_content = pd.DataFrame(columns=['INHOS_NO'])

                    # 使用 final_inhos_to_process 列表来确定要移除的记录
                    records_to_remove_set = set(final_inhos_to_process)

                    if not df_original_csv_content.empty and 'INHOS_NO' in df_original_csv_content.columns:
                        new_df_for_csv = df_original_csv_content[~df_original_csv_content['INHOS_NO'].isin(records_to_remove_set)]
                    else:
                        new_df_for_csv = pd.DataFrame(columns=['INHOS_NO']) # 如果原始为空或无INHOS_NO列，则新df也为空

                    # 保存回原CSV文件 (保留第一行ICD10范围)
                    with open(selected_csv_full_path, 'w', encoding='utf-8') as f_out:
                        f_out.write(f"{icd10_range}\n") # 写入ICD10范围和1个换行符
                        if not new_df_for_csv.empty:
                            # 只保存 INHOS_NO 列，不保存索引和表头
                            new_df_for_csv[['INHOS_NO']].to_csv(f_out, index=False, header=False, lineterminator='\n')

                    print(f"已从CSV文件 '{selected_csv_name_only}' 中移除 {len(records_to_remove_set)} 条本轮尝试处理的住院号，剩余 {len(new_df_for_csv)} 条。")
                    if len(new_df_for_csv) == 0:
                        print(f"CSV文件 '{selected_csv_name_only}' 中已无待处理住院号。")

                except Exception as e_csv_write:
                    print(f"自动更新CSV文件 '{selected_csv_name_only}' 时出错: {e_csv_write}")
            else:
                print(f"\n本轮没有计划处理的住院号，CSV文件 '{selected_csv_name_only}' 未被修改。")
            # 修改结束

            edit_csv_choice = input("\n是否需要手动编辑原始CSV文件中的住院号? (y/n): ").lower()
            # ... (后续手动编辑CSV的逻辑保持不变) ...

            edit_csv_choice = input("\n是否需要手动编辑原始CSV文件中的住院号? (y/n): ").lower()
            if edit_csv_choice == 'y':
                try:
                    # 重新读取最新的CSV内容进行编辑
                    df_edit_current = pd.read_csv(selected_csv_full_path, skiprows=1, header=None, names=['INHOS_NO_RAW'], dtype=str, skip_blank_lines=True)
                    if 'INHOS_NO_RAW' in df_edit_current.columns: # 确保列存在
                        df_edit_current.dropna(subset=['INHOS_NO_RAW'], inplace=True)
                        df_edit_current['INHOS_NO'] = df_edit_current['INHOS_NO_RAW'].astype(str).str.strip()
                        df_edit_current = df_edit_current[df_edit_current['INHOS_NO'] != '']
                    else: # 如果读取后没有该列（例如CSV只有表头或完全为空）
                        df_edit_current = pd.DataFrame(columns=['INHOS_NO'])


                    if df_edit_current.empty:
                        print(f"CSV文件 '{selected_csv_name_only}' (跳过首行后) 中没有剩余的住院号可编辑。")
                    else:
                        while True:
                            print(f"\n当前原始CSV文件 '{selected_csv_name_only}' 中的住院号列表 (共 {len(df_edit_current)} 条):")
                            for i, inhos_no_val_edit in enumerate(df_edit_current['INHOS_NO'], 1):
                                print(f"{i}. {inhos_no_val_edit}")

                            print("\n请选择操作:")
                            print("1. 删除单条住院号")
                            print("2. 批量删除住院号")
                            print("3. 保存更改并退出编辑")
                            print("4. 不保存更改退出编辑")

                            op_choice = input("请输入操作编号(1-4): ")

                            if op_choice == '1':
                                try:
                                    idx_to_del_str = input("请输入要删除的住院号的列表编号: ")
                                    idx_to_del = int(idx_to_del_str) - 1
                                    if 0 <= idx_to_del < len(df_edit_current):
                                        deleted_val = df_edit_current.iloc[idx_to_del]['INHOS_NO']
                                        df_edit_current = df_edit_current.drop(df_edit_current.index[idx_to_del]).reset_index(drop=True)
                                        print(f"已从编辑列表中删除住院号: {deleted_val}")
                                    else:
                                        print("无效的编号，请重试。")
                                except ValueError:
                                    print("输入无效，请输入数字编号。")

                            elif op_choice == '2':
                                indices_str = input("请输入要删除的住院号的列表编号 (用逗号分隔, 例如 1,3,5): ")
                                try:
                                    idx_list_to_del = [int(x.strip()) - 1 for x in indices_str.split(',') if x.strip().isdigit()]
                                    idx_list_to_del.sort(reverse=True)

                                    actual_deleted_count = 0
                                    for idx_val in idx_list_to_del:
                                        if 0 <= idx_val < len(df_edit_current):
                                            df_edit_current = df_edit_current.drop(df_edit_current.index[idx_val]).reset_index(drop=True)
                                            actual_deleted_count += 1
                                    print(f"已从编辑列表中删除 {actual_deleted_count} 条住院号。")
                                except ValueError:
                                    print("输入格式错误，请使用逗号分隔的有效数字编号。")

                            elif op_choice == '3':
                                with open(selected_csv_full_path, 'w', encoding='utf-8') as f_csv_out:
                                    f_csv_out.write(f"{icd10_range}\n")
                                    if not df_edit_current.empty:
                                        df_edit_current[['INHOS_NO']].to_csv(f_csv_out, index=False, header=False, lineterminator='\n')
                                print(f"已保存对CSV文件 '{selected_csv_name_only}' 的更改，剩余 {len(df_edit_current)} 条住院号。")
                                break

                            elif op_choice == '4':
                                print("未保存对CSV文件的更改，退出编辑。")
                                break
                            else:
                                print("无效的操作编号，请重试。")
                except Exception as e_csv_edit:
                    print(f"编辑CSV文件 '{selected_csv_name_only}' 时出错: {e_csv_edit}")
                    import traceback
                    traceback.print_exc()

        except FileNotFoundError:
            print(f"错误: CSV文件 {selected_csv_full_path} 未找到。请检查路径和文件名。")
        except pd.errors.ParserError:
            print(f"错误: 解析CSV文件 {selected_csv_name_only} 失败。请检查文件格式是否正确。")
        except ValueError as ve_main:
            print(f"CSV模式主流程中发生数值输入错误: {ve_main}")
        except Exception as e_main:
            print(f"处理CSV文件 {selected_csv_name_only if 'selected_csv_name_only' in locals() else '未知'} 或CSV模式主流程时发生未知错误: {e_main}")
            import traceback
            traceback.print_exc()

    else:
        print("无效的选择。程序退出。")

if __name__ == "__main__":
    # 可以在这里添加一些启动前的检查或打印，用于调试
    # print("脚本开始执行...")
    main()
    # print("脚本执行完毕.")

# To run this, you would also need the MedicalRecordConverter and MedicalDataProcessor classes defined above it,
# as well as the global constants like DB_CONFIG, DEFAULT_INHOS_NO, FIXED_OUTPUT_DIR.
# if __name__ == "__main__":
#     # Ensure MedicalRecordConverter and MedicalDataProcessor classes are defined
#     # Ensure global constants are defined
#     main()
