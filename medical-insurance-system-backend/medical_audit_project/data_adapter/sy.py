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

try:
    from .medical_configs import build_converter_config, build_module_queries
except ImportError:
    from medical_configs import build_converter_config, build_module_queries

try:
    from . import llm_extractors
except ImportError:
    try:
        import llm_extractors
    except ImportError:
        class _MissingLLMExtractors:
            def __getattr__(self, name):
                raise ImportError("未找到 llm_extractors.py，无法执行病历文书大模型抽取")

        llm_extractors = _MissingLLMExtractors()

try:
    from . import disease_rules
except ImportError:
    try:
        import disease_rules
    except ImportError:
        class _EmptyDiseaseRules:
            ICD10_DISEASE_RULES = {}
            ICD9_DISEASE_RULES = {}

        disease_rules = _EmptyDiseaseRules()

# =========================
# OceanBase 数据库配置
# =========================
DB_CONFIG = {
    "host": "10.114.96.57",
    "port": 12881,
    "user": "huali@tenant_xwjg",
    "password": "H@3.14lia",
    "database": "xwjg_yw",
    "charset": "utf8mb4"
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


def sanitize_path_component(value, default="未知"):
    text = str(value or "").strip()
    if not text or text.lower() in {"none", "null", "xxx"}:
        text = default
    return re.sub(r'[<>:"/\\|?*\r\n\t]+', "_", text).strip(" .") or default


def delete_old_files_for_inhos_no_recursive(result_root, inhos_no, current_files):
    current_files = {os.path.abspath(path) for path in current_files or []}
    if not result_root or not os.path.exists(result_root):
        return
    pattern = os.path.join(result_root, "**", f"patient_{inhos_no}_*.json")
    deleted_count = 0
    for file_path in glob.glob(pattern, recursive=True):
        if os.path.abspath(file_path) in current_files:
            continue
        try:
            os.remove(file_path)
            deleted_count += 1
        except Exception as e:
            print(f"    删除旧文件失败: {file_path} | {e}")
    if deleted_count:
        print(f"    共删除 {deleted_count} 个同住院号的旧文件")


class MedicalRecordConverter:
    def __init__(self):
        config = build_converter_config()
        self.module_mappings = config["module_mappings"]
        self.nursing_mapping = config["nursing_mapping"]
        self.assessment_mapping = config["assessment_mapping"]
        self.fields_to_concat = config["fields_to_concat"]
        self.fields_with_units = config["fields_with_units"]
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
                    elif module == "病案首页" and source == "DRG_ALGN_FLG":
                        raw_value = row.get(source)
                        if raw_value == 1 or str(raw_value).strip() == "1":
                            record[target] = "有"
                        else:
                            record[target] = "无"
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

    def build_default_record_for_module(self, module):
        if module == "护理记录":
            return {"护理记录名": "xxx", "时间": "xxx", "内容": "xxx"}
        if module == "用药信息":
            return {
                "药品名": "xxx",
                "药品类别": "xxx",
                "药品通用名": "xxx",
                "药品国家编码": "xxx",
                "药品开具次数": "0",
                "开药信息": [
                    {
                        "药品收费时间": "xxx",
                        "给药目的": "xxx",
                        "药物使用总剂量": "xxx",
                        "药品使用总剂量单位": "xxx",
                        "药物使用次剂量": "xxx",
                        "药品使用次剂量单位": "xxx",
                        "药品使用频次名称": "xxx"
                    }
                ],
            }
        mapping = self.module_mappings.get(module, {})
        record = {target: "xxx" for target in mapping.keys()}
        if module == "检验":
            record["检验结果"] = "xxx"
        return record
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
            order_no = row.get("ODR_NO", "")
            if not order_no or order_no == "NULL": continue
            if order_no not in orders_by_id:
                orders_by_id[order_no] = []
            orders_by_id[order_no].append(row)
        # 构建医嘱记录
        results = []
        for order_no, rows in orders_by_id.items():
            for row in rows:
                order_record = self.build_default_record_for_module("医嘱")
                order_record["医嘱号"] = self.format_value(order_no)

                for target, source in self.module_mappings.get("医嘱", {}).items():
                    if target == "医嘱号":
                        continue
                    if not source:
                        order_record[target] = "xxx"
                        continue

                    if target == "医嘱开始时间":
                        value = row.get(source) or row.get("ODR_OPN_DT_TM")
                        order_record[target] = self.format_date(value)
                        continue
                    if target == "医嘱停止时间":
                        value = row.get(source) or row.get("ODR_END_DT")
                        order_record[target] = self.format_date(value)
                        continue

                    if "时间" in target or "日期" in target:
                        order_record[target] = self.format_date(row.get(source))
                    else:
                        order_record[target] = self.format_value(row.get(source))

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
        处理用药信息结构
        用药信息 -> 药品信息 -> 开药信息(列表)
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

        # 构建最终结构
        result = []
        for medication_name, medication_info in medication_groups.items():
            # 计算药品开具次数
            prescription_count = len(medication_info["处方记录"])
            medication_info["药品开具次数"] = str(prescription_count)

            prescriptions = medication_info["处方记录"]
            prescriptions.sort(key=lambda x: x.get("药品收费时间", ""))

            # 构建药品信息结构（开药信息为列表）
            drug_info = {
                "药品名": medication_info["药品名"],
                "药品类别": medication_info["药品类别"],
                "药品通用名": medication_info["药品通用名"],
                "药品国家编码": medication_info["药品国家编码"],
                "药品开具次数": medication_info["药品开具次数"],
                "开药信息": prescriptions,
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
        self.verbose = os.environ.get("VERBOSE", "").strip().lower() in {"1", "true", "yes", "y"}
        self.model_pools = {
            "qwen_pool": [
                {"name": "qwen", "url": "http://127.0.0.1:9233/v1/chat/completions"},
                {"name": "qwen", "url": "http://127.0.0.1:9234/v1/chat/completions"},
                {"name": "qwen", "url": "http://127.0.0.1:9235/v1/chat/completions"},
                {"name": "qwen", "url": "http://127.0.0.1:9236/v1/chat/completions"},
            ],
            "qwen_legacy": [{"name": "qwen3-30b-a3b", "url": "http://localhost:54320/v1/chat/completions"}],
            "qwen2.5-7B": [{"name": "qwen2.5-7B", "url": "http://localhost:54322/v1/chat/completions"}],
        }
        self.pool_counters = {pool_name: 0 for pool_name in self.model_pools}
        self.max_workers = sum(len(pool) for pool in self.model_pools.values())

        self.module_assignments = {
            "入院记录": "qwen2.5-7B",
            "出院记录": "qwen2.5-7B",
            "上级医生查房记录": "qwen2.5-7B",
            "化疗记录": "qwen2.5-7B",
            "首次病程记录": "qwen2.5-7B",
        }

        self.lock = threading.Lock()

    def _log(self, message: str) -> None:
        if self.verbose:
            print(message)

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
        pool_name = self.module_assignments.get(module_name, "qwen_pool")
        return self.get_model_for_pool(pool_name)

    def get_model_for_pool(self, pool_name: str):
        pool_name = pool_name if pool_name in self.model_pools else "qwen_pool"
        pool = self.model_pools.get(pool_name) or self.model_pools["qwen_pool"]
        with self.lock:
            idx = self.pool_counters.get(pool_name, 0) % len(pool)
            self.pool_counters[pool_name] = idx + 1
        return pool[idx]

    def process_module_parallel(self, module_tasks):
        """并行处理多个模块任务"""
        results = {}

        # 使用线程池并行处理
        max_workers = min(self.max_workers, max(1, len(module_tasks)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_module = {}
            for module_name, prompt in module_tasks.items():
                model_config = self.get_model_for_module(module_name)
                self._log(f"分配模块 '{module_name}' 给模型 '{model_config['name']}'")

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
                    self._log(f"模块 '{module_name}' 处理完成")
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
        self._log(f"开始并行处理 {len(document_tasks)} 个文档...")
        results = {}

        # 使用线程池并行处理
        max_workers = min(self.max_workers, max(1, len(document_tasks)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_doc = {}
            for doc_type, (raw_data, process_func) in document_tasks.items():
                if raw_data:  # 只处理有数据的文档
                    self._log(f"提交文档 '{doc_type}' 到并行处理队列")
                    future = executor.submit(process_func, raw_data)
                    future_to_doc[future] = doc_type
                else:
                    try:
                        results[doc_type] = process_func(raw_data or [])
                    except Exception as e:
                        print(f"文档 '{doc_type}' 无数据且构建默认结果失败: {e}")
                        results[doc_type] = {}
                    self._log(f"文档 '{doc_type}' 无数据，使用默认结构")

            # 收集结果
            for future in as_completed(future_to_doc):
                doc_type = future_to_doc[future]
                try:
                    result = future.result()
                    results[doc_type] = result
                    self._log(f"文档 '{doc_type}' 处理完成")
                except Exception as e:
                    print(f"文档 '{doc_type}' 处理失败: {e}")
                    try:
                        _, process_func = document_tasks.get(doc_type, (None, None))
                        if process_func:
                            results[doc_type] = process_func([])
                        else:
                            results[doc_type] = {}
                    except Exception as e2:
                        print(f"文档 '{doc_type}' 构建默认结构失败: {e2}")
                        results[doc_type] = {}

        self._log("所有文档并行处理完成")
        return results

# 创建全局多模型API实例
multi_model_api = MultiModelAPI()

# 保持原有的单模型接口向后兼容
def send_chat_completion_request(model_name, message_content, temperature=0.01):
    if model_name == "qwen2.5-7B":
        model_config = multi_model_api.get_model_for_pool("qwen2.5-7B")
    elif model_name == "qwen_legacy":
        model_config = multi_model_api.get_model_for_pool("qwen_legacy")
    else:
        model_config = multi_model_api.get_model_for_pool("qwen_pool")
    return multi_model_api.send_chat_completion_request(model_config, message_content, temperature)

def chat_method(content):
    return send_chat_completion_request("qwen", content)

def chat_method_legacy(content):
    return send_chat_completion_request("qwen_legacy", content)


class MedicalDataProcessor:
    _batch_prefetch_cache = {}

    def get_main_icd9_from_oprt_exec(self) -> Dict[str, Any]:
        """Get the main ICD9 operation code from ODS_FACT_OPRT_EXEC_INFMT."""
        mdc_condition = f"AND MDC_ORG_CD = '{self.mdc_org_cd}'" if self.mdc_org_cd else ""
        query = f"""
            SELECT INHOS_NO, OPRT_CD, OPRT_NM, MAIN_OPRT_FLG
            FROM ODS_FACT_OPRT_EXEC_INFMT
            WHERE INHOS_NO = '{self.inhos_no}' {mdc_condition}
              AND MAIN_OPRT_FLG = 1
              AND (INVLD_FLG = 0 OR INVLD_FLG IS NULL)
            ORDER BY COALESCE(OPRT_DT_TM, CRT_TM) DESC
            LIMIT 1;
        """
        started_at = time.perf_counter()
        try:
            with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()
            print(f"SQL耗时[主要ICD9手术编码]: {time.perf_counter() - started_at:.3f}s，原始返回 {len(rows)} 条")
        except Exception as e:
            print(f"主要ICD9手术编码查询失败: {e}，耗时 {time.perf_counter() - started_at:.3f}s")
            return {"code": "", "name": "", "match_rate": 0}

        if not rows:
            return {"code": "", "name": "", "match_rate": 0}

        first_record = rows[0] if isinstance(rows, list) else {}
        if not isinstance(first_record, dict):
            return {"code": "", "name": "", "match_rate": 0}

        code = str(first_record.get("OPRT_CD") or "").strip()
        name = str(first_record.get("OPRT_NM") or "").strip()
        return {"code": code, "name": name, "match_rate": 100 if code else 0}

    def get_main_icd10_from_home_page(self) -> Dict[str, Any]:
        home_diag_records = self.execute_query("病案首页诊断信息")
        if not home_diag_records:
            diag_info_records = self.execute_query("诊断信息")
            main_diag_records = []
            for record in diag_info_records or []:
                main_flag = record.get("MAIN_DIAG_FLG")
                if main_flag == 1 or main_flag == 1.0 or str(main_flag).strip() == "1":
                    main_diag_records.append(record)
            home_diag_records = main_diag_records

        if not home_diag_records:
            return {"code": "未找到主诊断ICD10编码", "name": "未找到主诊断ICD10名称", "match_rate": 0}

        first_record = home_diag_records[0] if isinstance(home_diag_records, list) else {}
        if not isinstance(first_record, dict):
            return {"code": "未找到主诊断ICD10编码", "name": "未找到主诊断ICD10名称", "match_rate": 0}

        code = str(first_record.get("DIAG_CD") or "").strip()
        name = str(first_record.get("DIAG_NM") or "").strip()

        if not code:
            return {"code": "未找到主诊断ICD10编码", "name": name or "未找到主诊断ICD10名称", "match_rate": 0}

        return {"code": code, "name": name, "match_rate": 100}

    def extract_discharge_diagnosis_first_item(self, discharge_content: str) -> str:
        if not discharge_content:
            return "文本中未提及该内容"

        text = str(discharge_content).replace("\r\n", "\n").replace("\r", "\n")

        patterns = [
            r"出院诊断[：:]\s*(?:\n\s*)?1[\.\、\)]\s*(.+?)(?=\n\s*\d+[\.\、\)]|\n\s*(?:入院诊断|诊疗经过|出院情况|出院医嘱|出院指导|医师签名|医生签名)|\Z)",
            r"出院诊断[：:]\s*(.+?)(?=\n\s*(?:入院诊断|诊疗经过|出院情况|出院医嘱|出院指导|医师签名|医生签名)|\Z)",
        ]

        for pattern in patterns:
            m = re.search(pattern, text, flags=re.DOTALL)
            if not m:
                continue
            diag = (m.group(1) or "").strip()
            diag = re.sub(r"\s+", " ", diag).strip()
            diag = diag.strip("；;。.,，")
            if diag:
                return diag

        section = re.search(
            r"出院诊断[：:]\s*(.*?)(?=\n\s*(?:入院诊断|诊疗经过|出院情况|出院医嘱|出院指导|医师签名|医生签名)|\Z)",
            text,
            flags=re.DOTALL,
        )
        if section:
            section_text = (section.group(1) or "").strip()
            m = re.search(r"(?:^|\n)\s*1[\.\、\)]\s*(.+?)(?=\n|$)", section_text)
            if m:
                diag = (m.group(1) or "").strip()
                diag = re.sub(r"\s+", " ", diag).strip().strip("；;。.,，")
                if diag:
                    return diag
            first_line = section_text.split("\n", 1)[0].strip()
            first_line = re.sub(r"\s+", " ", first_line).strip().strip("；;。.,，")
            if first_line:
                return first_line

        return "文本中未提及该内容"

    def _parse_age_years(self, age_value) -> Optional[float]:
        if age_value is None:
            return None
        if isinstance(age_value, (int, float)):
            return float(age_value)
        age_str = str(age_value).strip()
        if not age_str or age_str.lower() == "null":
            return None
        match = re.search(r"\d+(?:\.\d+)?", age_str)
        if not match:
            return None
        try:
            return float(match.group(0))
        except Exception:
            return None

    def _age_requirement_ok(self, age_years: Optional[float], requirement: str) -> bool:
        if requirement is None or requirement == "":
            return True
        if age_years is None:
            return False
        if requirement == "adult":
            return age_years >= 18
        if requirement == "child":
            return 2 <= age_years < 18
        if requirement == "ddh":
            return (18 / 12) <= age_years <= 8
        return False

    def _icd10_starts_with_rule(self, icd10_code: str, rule_value: str) -> bool:
        if not icd10_code or not rule_value:
            return False
        if any(ch in rule_value for ch in ("x", "X", "*")):
            regex_parts = []
            for ch in rule_value:
                if ch in ("x", "X"):
                    regex_parts.append(".")
                elif ch == "*":
                    regex_parts.append(".*")
                else:
                    regex_parts.append(re.escape(ch))
            pattern = "^" + "".join(regex_parts)
            return re.match(pattern, icd10_code) is not None
        return icd10_code.startswith(rule_value)

    def _rules_match_code(self, code, rules, code_type="icd10") -> bool:
        code = str(code or "").strip().upper()
        if not code:
            return False
        for rule in rules or []:
            rule_type = rule.get("type")
            rule_value = str(rule.get("value") or "").strip().upper()
            if rule_type == "starts_with" and self._icd10_starts_with_rule(code, rule_value):
                return True
            if rule_type == "range" and code_type == "icd10":
                in_range, _ = self.is_icd10_in_range(code, rule_value)
                if in_range:
                    return True
            if rule_type == "range" and code_type != "icd10":
                if self._is_code_in_generic_range(code, rule_value):
                    return True
        return False

    def _is_code_in_generic_range(self, code, range_expression) -> bool:
        code = str(code or "").strip().upper()
        expr = str(range_expression or "").strip().upper()
        if not code or not expr:
            return False

        def normalize(value):
            m = re.match(r"^([A-Z]*)(\d+(?:\.\d+)?)", str(value or "").strip().upper())
            if not m:
                return None
            prefix = m.group(1)
            digits = re.sub(r"\D", "", m.group(2)).ljust(10, "0")
            return prefix, digits

        code_norm = normalize(code)
        if not code_norm:
            return False

        for part in re.split(r"[,，、]或|或(?!\w)|、|,|;|；", expr):
            part = part.strip()
            if not part:
                continue
            if "至" in part or "-" in part:
                separator = "至" if "至" in part else "-"
                start, end = [item.strip() for item in part.split(separator, 1)]
                start_norm = normalize(start)
                end_norm = normalize(end)
                if start_norm and end_norm and code_norm[0] == start_norm[0] == end_norm[0]:
                    if start_norm[1] <= code_norm[1] <= end_norm[1]:
                        return True
            elif code.startswith(part):
                return True
        return False

    def match_disease_name_by_icd10_and_age(self, icd10_code, age_value, secondary_icd10_codes=None, icd9_code=None) -> str:
        matches = self.match_diseases_by_codes(icd10_code, age_value, secondary_icd10_codes=secondary_icd10_codes, icd9_code=icd9_code)
        return matches[0]["disease"] if matches else "其他病种"

    def match_diseases_by_codes(self, icd10_code, age_value, secondary_icd10_codes=None, icd9_code=None) -> List[Dict[str, str]]:
        code = str(icd10_code or "").strip().upper()
        operation_code = str(icd9_code or "").strip().upper()
        secondary_codes = [
            str(item or "").strip().upper()
            for item in (secondary_icd10_codes or [])
            if str(item or "").strip()
        ]
        age_years = self._parse_age_years(age_value)
        matched = []
        seen = set()

        def add_match(match_type, disease_name, **extra):
            if not disease_name or disease_name in seen:
                return
            seen.add(disease_name)
            item = {"type": match_type, "disease": disease_name}
            item.update(extra)
            matched.append(item)

        for _, disease_info in disease_rules.ICD10_DISEASE_RULES.items():
            if disease_info.get("dual_match") or disease_info.get("icd9_rules"):
                requirement = disease_info.get("age_requirement")
                if requirement and not self._age_requirement_ok(age_years, requirement):
                    continue
                icd10_rules = (
                    disease_info.get("icd10_rules")
                    or disease_info.get("rules")
                    or disease_info.get("main_diagnosis_rules")
                    or []
                )
                icd9_rules = disease_info.get("icd9_rules") or []
                if self._rules_match_code(code, icd10_rules, "icd10") and self._rules_match_code(operation_code, icd9_rules, "icd9"):
                    add_match("DUAL_MATCH", disease_info.get("name") or "其他病种", icd10_code=code, icd9_code=operation_code)
                continue
            if disease_info.get("require_secondary_diagnosis"):
                main_rules = disease_info.get("main_diagnosis_rules") or []
                secondary_rules = disease_info.get("secondary_diagnosis_rules") or []
                if not self._rules_match_code(code, main_rules, "icd10"):
                    continue
                if any(self._rules_match_code(sec_code, secondary_rules, "icd10") for sec_code in secondary_codes):
                    add_match("ICD10_WITH_SECONDARY", disease_info.get("name") or "其他病种", code=code)
                continue

            requirement = disease_info.get("age_requirement")
            if requirement and not self._age_requirement_ok(age_years, requirement):
                continue

            rule_list = (
                disease_info.get("rules")
                or disease_info.get("icd10_rules")
                or disease_info.get("main_diagnosis_rules")
                or []
            )
            if self._rules_match_code(code, rule_list, "icd10"):
                add_match("ICD10", disease_info.get("name") or "其他病种", code=code)

        for _, disease_info in disease_rules.ICD9_DISEASE_RULES.items():
            if self._rules_match_code(operation_code, disease_info.get("rules") or [], "icd9"):
                add_match("ICD9", disease_info.get("name") or "其他病种", code=operation_code)

        return matched

    def get_disease_info_by_name(self, disease_name):
        if disease_name in disease_rules.ICD10_DISEASE_RULES:
            return disease_rules.ICD10_DISEASE_RULES[disease_name]
        if disease_name in disease_rules.ICD9_DISEASE_RULES:
            return disease_rules.ICD9_DISEASE_RULES[disease_name]
        return {"name": disease_name, "folder": disease_name}

    def get_disease_folder_name(self, disease_name):
        disease_info = self.get_disease_info_by_name(disease_name)
        return disease_info.get("folder") or disease_info.get("name") or disease_name or "其他病种"

    def get_department_folder_name(self, patient_basic_records=None, modules_result=None, result=None):
        candidates = []
        for records in (patient_basic_records,):
            if isinstance(records, list) and records and isinstance(records[0], dict):
                candidates.extend([
                    records[0].get("DSCG_DPT_NM"),
                    records[0].get("DSCG_DEPT_NM"),
                    records[0].get("ADMN_DPT_NM"),
                ])
        for module_name in ("病案首页", "基本信息"):
            module_data = (modules_result or {}).get(module_name) if modules_result else None
            if isinstance(module_data, list) and module_data and isinstance(module_data[0], dict):
                candidates.extend([
                    module_data[0].get("出院科别"),
                    module_data[0].get("科别"),
                    module_data[0].get("科室"),
                    module_data[0].get("ADMN_DPT_NM"),
                ])
            elif isinstance(module_data, dict):
                candidates.extend([
                    module_data.get("出院科别"),
                    module_data.get("科别"),
                    module_data.get("科室"),
                    module_data.get("ADMN_DPT_NM"),
                ])
        if isinstance(result, dict):
            basic_info = result.get("基本信息")
            if isinstance(basic_info, dict):
                candidates.extend([basic_info.get("科别"), basic_info.get("科室"), basic_info.get("专科名称")])
        for value in candidates:
            text = str(value or "").strip()
            if text and text.lower() not in {"none", "null", "xxx"}:
                return text
        return "未知科别"

    def save_result_by_disease_structure(self, result, output_root, output_file_name, disease_matches, department_name):
        saved_files = []
        if not disease_matches:
            disease_matches = [{"type": "UNMATCHED", "disease": "其他病种"}]
        dept_dir_name = sanitize_path_component(department_name, "未知科别")
        for disease_match in disease_matches:
            disease_name = disease_match.get("disease") or "其他病种"
            disease_dir_name = sanitize_path_component(self.get_disease_folder_name(disease_name), "其他病种")
            output_dir = os.path.join(output_root, dept_dir_name, disease_dir_name)
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, output_file_name)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            saved_files.append(output_path)
            print(f"数据已导出到: {output_path}")
        return saved_files

    def is_icd10_in_range(self, icd10_code, range_expression):
        if not icd10_code or icd10_code == "未找到匹配ICD10编码":
            return False, None

        code = str(icd10_code).strip().upper()
        expr = str(range_expression or "").replace("\ufeff", "").strip()
        cache_key = (code, expr)

        cached = getattr(self, "_icd10_range_cache", {}).get(cache_key)
        if cached is not None:
            return cached

        if not hasattr(self, "_icd10_range_parts_cache"):
            self._icd10_range_parts_cache = {}
        if not hasattr(self, "_icd10_range_cache"):
            self._icd10_range_cache = {}

        range_parts = self._icd10_range_parts_cache.get(expr)
        if range_parts is None:
            range_parts = []
            for part in re.split(r"[,，、]或|或(?!\w)|、|,|;|；", expr):
                part = part.strip()
                if part:
                    range_parts.append(part)
            self._icd10_range_parts_cache[expr] = range_parts

        verbose = bool(getattr(self, "verbose", False))
        if verbose:
            print(f"检查编码 {code} 是否在范围 {expr} 内")

        for range_part in range_parts:
            try:
                if "至" in range_part or "-" in range_part:
                    separator = "至" if "至" in range_part else "-"
                    start, end = range_part.split(separator, 1)
                    start, end = start.strip().upper(), end.strip().upper()

                    if code == start or code == end:
                        result = (True, range_part)
                        self._icd10_range_cache[cache_key] = result
                        return result

                    start_match = re.match(r"([A-Z]+)(\d+)(.*)", start)
                    end_match = re.match(r"([A-Z]+)(\d+)(.*)", end)
                    code_match = re.match(r"([A-Z]+)(\d+)(.*)", code)
                    if not (start_match and end_match and code_match):
                        continue

                    start_prefix, start_num, start_suffix = start_match.groups()
                    end_prefix, end_num, end_suffix = end_match.groups()
                    code_prefix, code_num, code_suffix = code_match.groups()

                    if code_prefix != start_prefix or code_prefix != end_prefix:
                        continue

                    if int(start_num) <= int(code_num) <= int(end_num):
                        if not (start_suffix or end_suffix or code_suffix):
                            result = (True, range_part)
                            self._icd10_range_cache[cache_key] = result
                            return result
                        if code_suffix and not start_suffix and not end_suffix:
                            result = (True, range_part)
                            self._icd10_range_cache[cache_key] = result
                            return result
                        if start_suffix and end_suffix and code_suffix:
                            if code_num == start_num and code_suffix < start_suffix:
                                continue
                            if code_num == end_num and code_suffix > end_suffix:
                                continue
                            result = (True, range_part)
                            self._icd10_range_cache[cache_key] = result
                            return result

                elif "x" in range_part.lower() or "X" in range_part or "*" in range_part:
                    pattern = range_part.replace("*", ".*")
                    pattern = pattern.replace("x", "\\d").replace("X", "\\d")
                    pattern = f"^{pattern}$"
                    if re.match(pattern, code):
                        result = (True, range_part)
                        self._icd10_range_cache[cache_key] = result
                        return result

                    if "." in range_part and "." in code:
                        code_parts = code.split(".", 1)
                        pattern_parts = range_part.split(".", 1)
                        if code_parts[0] == pattern_parts[0] and (
                            "x" in pattern_parts[1].lower() or "*" in pattern_parts[1]
                        ):
                            result = (True, range_part)
                            self._icd10_range_cache[cache_key] = result
                            return result

                elif range_part.endswith("+"):
                    base_code = range_part[:-1].strip().upper()
                    if code.startswith(base_code):
                        result = (True, range_part)
                        self._icd10_range_cache[cache_key] = result
                        return result

                else:
                    rp = str(range_part).strip().upper()
                    if code == rp:
                        result = (True, range_part)
                        self._icd10_range_cache[cache_key] = result
                        return result

                    if "." not in rp:
                        code_prefix_match = re.match(r"([A-Z]+\d+)", code)
                        if code_prefix_match and code_prefix_match.group(1) == rp:
                            result = (True, range_part)
                            self._icd10_range_cache[cache_key] = result
                            return result

                    if "." in code:
                        code_base = code.split(".", 1)[0]
                        if code_base == rp:
                            result = (True, range_part)
                            self._icd10_range_cache[cache_key] = result
                            return result

                    if "." not in rp and code.startswith(rp + "."):
                        result = (True, range_part)
                        self._icd10_range_cache[cache_key] = result
                        return result

                    if "." in rp and code.startswith(rp):
                        result = (True, range_part)
                        self._icd10_range_cache[cache_key] = result
                        return result

            except Exception as e:
                if verbose:
                    print(f"处理范围 {range_part} 时出错: {e}")

        result = (False, None)
        self._icd10_range_cache[cache_key] = result
        return result
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

    def __init__(self, inhos_no=DEFAULT_INHOS_NO, mdc_org_cd=None):
        self.inhos_no = inhos_no
        self.mdc_org_cd = mdc_org_cd
        self.converter = MedicalRecordConverter()
        self.extracted_vital_signs = {"T": "xxx", "P": "xxx", "R": "xxx", "BP高": "xxx", "BP低": "xxx"}
        self.verbose = os.environ.get("VERBOSE", "").strip().lower() in {"1", "true", "yes", "y"}
        self._icd10_range_cache = {}
        self._icd10_range_parts_cache = {}
        self._document_records_cache = None
        self._patient_basic_records_cache = None
        self._prefetched_module_records = self._batch_prefetch_cache.get(self.inhos_no, {})

        # 数据库连接代码
        self.connection = None
        try:
            # 使用pymysql直接连接 OceanBase（MySQL 模式）
            connect_started_at = time.perf_counter()
            self.connection = pymysql.connect(
                host=DB_CONFIG["host"],
                port=DB_CONFIG["port"],
                user=DB_CONFIG["user"],
                password=DB_CONFIG["password"],
                database=DB_CONFIG["database"],
                charset=DB_CONFIG["charset"]
            )
            print(f"数据库连接已建立，耗时 {time.perf_counter() - connect_started_at:.3f}s")
        except Exception as e:
            print(f"数据库连接失败: {e}")
            sys.exit(1)

        # 设置模块查询语句
        self.module_queries = build_module_queries(self.inhos_no, self.mdc_org_cd)

    @classmethod
    def clear_batch_prefetch_cache(cls):
        cls._batch_prefetch_cache = {}

    @classmethod
    def batch_prefetch_records(cls, inhos_nos, batch_size=50, mdc_org_cd=None):
        """批量预取按住院号直查的大表，避免批量模式下同一张大表被反复全表扫描。"""
        inhos_nos = [str(no).strip() for no in inhos_nos if str(no).strip()]
        if not inhos_nos:
            return

        cls._batch_prefetch_cache = {inhos_no: {} for inhos_no in inhos_nos}
        try:
            batch_size = int(batch_size or 50)
        except ValueError:
            batch_size = 50
        batch_size = max(1, min(batch_size, 200))

        print(f"批量预取SQL缓存已启用：共 {len(inhos_nos)} 个住院号，每批 {batch_size} 个")
        for start in range(0, len(inhos_nos), batch_size):
            chunk = inhos_nos[start:start + batch_size]
            print(f"批量预取进度：{start + 1}-{start + len(chunk)}/{len(inhos_nos)}")
            cls._prefetch_one_chunk(chunk, mdc_org_cd)

    @classmethod
    def _prefetch_one_chunk(cls, inhos_nos, mdc_org_cd=None):
        quoted = ", ".join(cls._quote_sql_value(no) for no in inhos_nos)
        mdc_org_cd = cls._quote_sql_value(mdc_org_cd) if mdc_org_cd else None
        mdc_condition = f"AND MDC_ORG_CD = {mdc_org_cd}" if mdc_org_cd else ""

        queries = {
            "入出院文书合并": f"""
                SELECT *, INVLD_FLG
                FROM ODS_FACT_INHOS_MDC_HTR_RCD_S
                WHERE INHOS_NO IN ({quoted}) {mdc_condition};
            """,
            "病程文书合并": f"""
                SELECT *, INVLD_FLG
                FROM ODS_FACT_INHOS_CRS_RCD_S
                WHERE INHOS_NO IN ({quoted}) {mdc_condition};
            """,
            "医嘱": f"""
                SELECT ODR_NO, ODR_GRP_NO, ODR_OPN_DT_TM, ODR_STRT_DT, ODR_END_DT, ODR_SQNC_NO, INHOS_NO, ODR_ITM_TP_NM,
                    ODR_ITM_TP_CD, ODR_EXEC_STRT_DT, ODR_EXEC_CPLT_DT, ODR_EXEC_STTS_NM,
                    ODR_STP_DT_TM, ODR_ITM_CD, ODR_ITM_NM, DRG_SPCF, DRG_USE_ONCE_DOSG,
                    DRG_USE_ONCE_DOSG_UNT, DRG_USE_TOT_DOSG, DRG_USE_TOT_DOSG_UNT,
                    DOS_RUT_NM, DRG_USE_FRQ_NM, INVLD_FLG
                FROM ODS_FACT_INHOS_ODR_INFMT
                WHERE INHOS_NO IN ({quoted}) {mdc_condition};
            """,
            "诊断": f"""
                SELECT INHOS_NO, DIAG_ICD10_CD, DIAG_ICD10_NM, DIAG_RCD_NO, DIAG_DT, DIAG_DSCPT, DIAG_CGY_NM, DIAG_CD, INVLD_FLG
                FROM ODS_FACT_INHOS_DIAG_INFMT
                WHERE INHOS_NO IN ({quoted}) {mdc_condition};
            """,
            "诊断信息": f"""
                SELECT INHOS_NO, DIAG_NM, DIAG_CD, DIAG_SRL_NO, MAIN_DIAG_FLG
                FROM ODS_FACT_MDC_RCD_HMPG_DIAG
                WHERE INHOS_NO IN ({quoted}) {mdc_condition};
            """,
            "病案首页诊断信息": f"""
                SELECT INHOS_NO, DIAG_CD, DIAG_NM, INHOS_CDT_CD, MAIN_DIAG_FLG
                FROM ODS_FACT_MDC_RCD_HMPG_DIAG
                WHERE INHOS_NO IN ({quoted}) {mdc_condition} AND MAIN_DIAG_FLG = 1;
            """,
            "病案首页手术信息": f"""
                SELECT INHOS_NO, OPRT_CD, OPRT_NM, MAIN_OPRT_FLG
                FROM ODS_FACT_MDC_RCD_HMPG_OPRT
                WHERE INHOS_NO IN ({quoted}) {mdc_condition};
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
                    fee.FEE_CGY_NM,
                    fee.PRM_KEY,
                    fee.CHRG_RTRN_FLG,
                    fee.MDC_ORG_CD,
                    fee.INVLD_FLG
                FROM ODS_FACT_INHOS_FEE_DTL fee
                WHERE fee.INHOS_NO IN ({quoted}) {mdc_condition};
            """,
            "医保": f"""
                SELECT DISTINCT INHOS_NO, MDCR_CGY_CD, MDCR_CGY_NM, INVLD_FLG
                FROM ODS_FACT_INHOS_FEE_STLMT
                WHERE INHOS_NO IN ({quoted}) {mdc_condition};
            """,
            "患者基础信息": f"""
                SELECT DSCG_DPT_NM, ADMN_DPT_NM, ADMN_DT_TM, DSCG_DT_TM, NM, GDR_NM, AGE, AGE_UNT, INHOS_NO, INVLD_FLG
                FROM ODS_FACT_MDC_RCD_HMPG
                WHERE INHOS_NO IN ({quoted}) {mdc_condition};
            """,
            "检查": f"""
                SELECT DISTINCT
                    rcd.INHOS_NO as INHOS_NO, rcd.EXAM_RCD_NO as EXAM_RCD_NO, rcd.EXAM_ITM_TP_NM, rcd.EXAM_PRT_NM, rcd.EXAM_ITM_NM,
                    rcd.EXAM_PRCS_DSCPT, rcd.APL_DT_TM, rcd.EXAM_DT,
                    rpt.EXAM_RPT_RSLT_OBJCT, rpt.EXAM_RSLT, rpt.EXAM_RPT_RSLT_SBJCT, rpt.EXAM_RPT_DT,
                    rpt.EXAM_RCD_NO as RPT_EXAM_RCD_NO,
                    rcd.INVLD_FLG as RCD_INVLD_FLG, rpt.INVLD_FLG as RPT_INVLD_FLG
                FROM ODS_FACT_EXAM_RCD rcd
                LEFT JOIN ODS_FACT_EXAM_RPT rpt ON rcd.EXAM_RCD_NO = rpt.EXAM_RCD_NO AND rcd.MDC_ORG_CD = rpt.MDC_ORG_CD
                WHERE rcd.INHOS_NO IN ({quoted}) {mdc_condition};
            """,
            "检验": f"""
                SELECT DISTINCT
                    rcd.INHOS_NO as RCD_INHOS_NO, rcd.TEST_RCD_NO, rcd.APL_DT_TM, rcd.TEST_DT, rcd.TEST_RPT_DT,
                    rcd.TEST_ITM_NM as RCD_TEST_ITM_NM, rcd.TEST_ITM_TP_NM, rslt.TEST_RSLT, rslt.TEST_RSLT_VLU,
                    rslt.TEST_RSLT_VLU_UNT, rslt.NML_VLU_MAX, rslt.NML_VLU_MIN, rslt.TEST_ITM_NM as RSLT_TEST_ITM_NM,
                    rslt.TEST_CHD_ITM_CD, rslt.TEST_CHD_ITM_NM,
                    rcd.TEST_RPT_NO as RCD_TEST_RPT_NO, rslt.TEST_RPT_NO as RSLT_TEST_RPT_NO,
                    rcd.INVLD_FLG as RCD_INVLD_FLG, rslt.INVLD_FLG as RSLT_INVLD_FLG
                FROM ODS_FACT_TEST_RCD rcd
                LEFT JOIN ODS_FACT_TEST_RPT_CVT_RSLT rslt
                ON rcd.TEST_RPT_NO = rslt.TEST_RPT_NO AND rcd.TEST_ITM_NM = rslt.TEST_ITM_NM AND rcd.MDC_ORG_CD = rslt.MDC_ORG_CD
                WHERE rcd.INHOS_NO IN ({quoted}) {mdc_condition};
            """,
        }

        connection = None
        try:
            connection = pymysql.connect(
                host=DB_CONFIG["host"],
                port=DB_CONFIG["port"],
                user=DB_CONFIG["user"],
                password=DB_CONFIG["password"],
                database=DB_CONFIG["database"],
                charset=DB_CONFIG["charset"]
            )
            for module, query in queries.items():
                started_at = time.perf_counter()
                try:
                    with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                        cursor.execute(query)
                        rows = cursor.fetchall()
                    grouped = cls._group_prefetch_rows(module, rows)
                    for inhos_no in inhos_nos:
                        cls._batch_prefetch_cache.setdefault(inhos_no, {})[module] = grouped.get(inhos_no, [])
                    print(f"批量预取[{module}]: {time.perf_counter() - started_at:.3f}s，返回 {len(rows)} 条")
                except Exception as e:
                    print(f"批量预取失败[{module}]: {e}，耗时 {time.perf_counter() - started_at:.3f}s")
                    for inhos_no in inhos_nos:
                        cls._batch_prefetch_cache.setdefault(inhos_no, {})[module] = []
        finally:
            if connection:
                try:
                    connection.close()
                except Exception:
                    pass

    @staticmethod
    def _quote_sql_value(value):
        return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"

    @classmethod
    def _group_prefetch_rows(cls, module, rows):
        grouped = {}
        for row in rows or []:
            inhos_no = (
                row.get("INHOS_NO")
                or row.get("RCD_INHOS_NO")
                or row.get("M_INHOS_NO")
                or row.get("D_INHOS_NO")
                or row.get("T_INHOS_NO")
                or row.get("A_INHOS_NO")
                or row.get("DC_INHOS_NO")
            )
            if not inhos_no:
                continue
            if cls._is_invalid_record(row):
                continue
            clean_row = {k: v for k, v in row.items() if "INVLD_FLG" not in k}
            grouped.setdefault(str(inhos_no), []).append(clean_row)
        return grouped

    @staticmethod
    def _is_invalid_record(record):
        for key, value in record.items():
            if "INVLD_FLG" in key and (value == 1 or value == "1" or value == 1.0):
                return True
        return False

    def _query_tables(self, query):
        return sorted(set(re.findall(r'\b(?:FROM|JOIN)\s+([`A-Za-z0-9_\.]+)', query, flags=re.IGNORECASE)))

    def _diagnose_query_plan(self, module, query, connection=None):
        if os.environ.get("SQL_DIAGNOSE", "").strip().lower() not in {"1", "true", "yes", "y"}:
            return
        sql = query.strip().rstrip(";")
        if not sql.lower().startswith("select"):
            return
        conn = connection or self.connection
        started_at = time.perf_counter()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(f"EXPLAIN {sql}")
                plan_rows = cursor.fetchall()
            print(f"SQL诊断[{module}]: 表={self._query_tables(query)}，EXPLAIN耗时 {time.perf_counter() - started_at:.3f}s")
            for row in plan_rows:
                table = row.get("table") or row.get("TABLE") or row.get("Table")
                access_type = row.get("type") or row.get("TYPE") or row.get("access_type")
                possible_keys = row.get("possible_keys") or row.get("POSSIBLE_KEYS")
                key = row.get("key") or row.get("KEY")
                rows = row.get("rows") or row.get("ROWS")
                extra = row.get("Extra") or row.get("extra")
                if any(value is not None for value in (table, access_type, possible_keys, key, rows, extra)):
                    print(f"SQL计划[{module}]: table={table}, type={access_type}, possible_keys={possible_keys}, key={key}, rows={rows}, extra={extra}")
                else:
                    print(f"SQL计划原始[{module}]: {row}")
        except Exception as e:
            print(f"SQL诊断[{module}]失败: {e}，耗时 {time.perf_counter() - started_at:.3f}s")

    def execute_query(self, module):
        """执行查询"""
        if module in self._prefetched_module_records:
            records = self._prefetched_module_records.get(module, [])
            print(f"批量预取缓存命中[{module}]: {len(records)} 条")
            if module in self._document_modules():
                return self._normalize_document_records(records)
            return records

        query = self.module_queries.get(module)
        if not query:
            print(f"错误: 未找到模块 '{module}' 的查询语句")
            return []

        started_at = time.perf_counter()
        try:
            print(f"执行查询: {module}")
            print(f"SQL阶段[{module}]: 准备执行，涉及表 {self._query_tables(query)}")
            self._diagnose_query_plan(module, query)

            # 创建游标
            with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
                # 执行SQL查询
                execute_started_at = time.perf_counter()
                cursor.execute(query)
                execute_elapsed = time.perf_counter() - execute_started_at
                # 获取所有结果
                fetch_started_at = time.perf_counter()
                results = cursor.fetchall()
                fetch_elapsed = time.perf_counter() - fetch_started_at
            query_elapsed = time.perf_counter() - started_at
            print(
                f"SQL阶段耗时[{module}]: execute={execute_elapsed:.3f}s, "
                f"fetch={fetch_elapsed:.3f}s, total={query_elapsed:.3f}s，原始返回 {len(results)} 条"
            )

            if not results:
                print(f"查询结果为空，总耗时 {time.perf_counter() - started_at:.3f}s")
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
            if module in self._document_modules():
                print(f"SQL处理耗时[{module}]: {time.perf_counter() - started_at:.3f}s")
                return self._normalize_document_records(filtered_records)
            print(f"SQL处理耗时[{module}]: {time.perf_counter() - started_at:.3f}s")
            return filtered_records

        except Exception as e:
            print(f"查询执行错误: {e}，耗时 {time.perf_counter() - started_at:.3f}s")
            # 对于特定的表不存在错误，给出更明确的提示
            if "doesn't exist" in str(e) and module == "护理记录":
                print(f"警告: {module}模块的某些表不存在，尝试使用备用查询方法")
                return []  # 或者调用一个备用方法
            return []

    def _create_db_connection(self):
        return pymysql.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            database=DB_CONFIG["database"],
            charset=DB_CONFIG["charset"]
        )

    def execute_query_with_new_connection(self, module):
        """并行查询专用：每个线程使用独立数据库连接。"""
        query = self.module_queries.get(module)
        if not query:
            print(f"错误: 未找到模块 '{module}' 的查询语句")
            return []

        started_at = time.perf_counter()
        connection = None
        try:
            print(f"执行并行查询: {module}")
            print(f"SQL阶段[{module}][parallel]: 准备连接，涉及表 {self._query_tables(query)}")
            connect_started_at = time.perf_counter()
            connection = self._create_db_connection()
            connect_elapsed = time.perf_counter() - connect_started_at
            print(f"SQL阶段[{module}][parallel]: connect={connect_elapsed:.3f}s")
            self._diagnose_query_plan(f"{module}[parallel]", query, connection=connection)
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                execute_started_at = time.perf_counter()
                cursor.execute(query)
                execute_elapsed = time.perf_counter() - execute_started_at
                fetch_started_at = time.perf_counter()
                results = cursor.fetchall()
                fetch_elapsed = time.perf_counter() - fetch_started_at
            query_elapsed = time.perf_counter() - started_at
            print(
                f"SQL阶段耗时[{module}][parallel]: connect={connect_elapsed:.3f}s, "
                f"execute={execute_elapsed:.3f}s, fetch={fetch_elapsed:.3f}s, "
                f"total={query_elapsed:.3f}s，原始返回 {len(results)} 条"
            )

            if not results:
                print(f"查询结果为空，总耗时 {time.perf_counter() - started_at:.3f}s")
                return []

            filter_started_at = time.perf_counter()
            filter_started_at = time.perf_counter()
            filter_started_at = time.perf_counter()
            filtered_records = []
            record_count = 0
            filtered_count = 0
            for record in results:
                record_count += 1
                is_valid = True
                for key in record.keys():
                    if 'INVLD_FLG' in key:
                        invld_value = record[key]
                        if invld_value == 1 or invld_value == '1' or invld_value == 1.0:
                            is_valid = False
                            filtered_count += 1
                            break
                if is_valid:
                    filtered_records.append({k: v for k, v in record.items() if 'INVLD_FLG' not in k})

            filter_elapsed = time.perf_counter() - filter_started_at
            filter_elapsed = time.perf_counter() - filter_started_at
            filter_elapsed = time.perf_counter() - filter_started_at
            print(
                f"过滤前共 {record_count} 条记录，过滤掉 {filtered_count} 条无效记录，剩余 {len(filtered_records)} 条记录")
            print(f"SQL阶段耗时[{module}]: python_filter={filter_elapsed:.3f}s")
            print(f"SQL阶段耗时[{module}][parallel]: python_filter={filter_elapsed:.3f}s")
            print(f"SQL阶段耗时[{module}]: python_filter={filter_elapsed:.3f}s")
            if module in self._document_modules():
                print(f"SQL处理耗时[{module}][parallel]: {time.perf_counter() - started_at:.3f}s")
                return self._normalize_document_records(filtered_records)
            print(f"SQL处理耗时[{module}][parallel]: {time.perf_counter() - started_at:.3f}s")
            return filtered_records
        except Exception as e:
            print(f"并行查询执行错误[{module}]: {e}，耗时 {time.perf_counter() - started_at:.3f}s")
            return []
        finally:
            if connection:
                try:
                    connection.close()
                except Exception:
                    pass

    def _document_modules(self):
        return {
            "入院记录",
            "出院记录",
            "首次病程记录",
            "上级医生查房记录",
            "日常病程记录",
            "化疗记录",
            "在院评估单",
            "手术记录详情",
            "入出院文书合并",
            "病程文书合并"
        }

    def _normalize_document_records(self, records):
        if not records:
            return []
        if all(r.get("DCMT_CTT") for r in records):
            return records
        if not any("ITM_NM" in r or "ITM_VLU" in r for r in records):
            return records
        grouped = {}
        for record in records:
            key = self._build_doc_group_key(record)
            grouped.setdefault(key, []).append(record)
        combined_records = []
        for group_records in grouped.values():
            combined_record = dict(group_records[0])
            dcmt_ctt = next((r.get("DCMT_CTT") for r in group_records if r.get("DCMT_CTT")), None)
            combined_record["DCMT_CTT"] = dcmt_ctt or self._join_item_lines(group_records)
            combined_records.append(combined_record)
        return combined_records

    def _build_doc_group_key(self, record):
        base = [record.get("INHOS_NO"), record.get("RCD_TP_NM")]
        if record.get("INHOS_MDC_HTR_RCD_NO"):
            base.append(record.get("INHOS_MDC_HTR_RCD_NO"))
        elif record.get("OPRT_RCD_NO"):
            base.append(record.get("OPRT_RCD_NO"))
        elif record.get("INHOS_CRS_RCD_NO"):
            base.append(record.get("INHOS_CRS_RCD_NO"))
        return tuple(base)

    def _join_item_lines(self, records):
        items = []
        for record in self._sorted_doc_items(records):
            itm_nm = str(record.get("ITM_NM") or "").strip()
            itm_vlu = str(record.get("ITM_VLU") or "").strip()
            if not itm_nm and not itm_vlu:
                continue
            if itm_nm and itm_vlu:
                line = f"{itm_nm}：{itm_vlu}"
            elif itm_nm:
                line = itm_nm
            else:
                line = itm_vlu
            items.append(line)
        return "\n".join(items)

    def _sorted_doc_items(self, records):
        order_fields = ["ITM_SRL_NO", "ITM_SEQ", "ITM_ORD_NO", "SEQ_NO", "SRT_NO"]
        def order_key(record):
            for field in order_fields:
                value = record.get(field)
                if value not in (None, "", "NULL"):
                    return value
            return 0
        return sorted(records, key=order_key)

    def execute_document_queries(self):
        """一次性读取文书数据，再按文书类型拆分，减少重复扫表。"""
        if self._document_records_cache is not None:
            return self._document_records_cache

        cache = {
            "入院记录": [],
            "出院记录": [],
            "首次病程记录": [],
            "上级医生查房记录": [],
            "日常病程记录": [],
            "化疗记录": [],
            "在院评估单": [],
        }

        htr_records = self.execute_query("入出院文书合并")
        for record in htr_records or []:
            record_type = str(record.get("RCD_TP_NM") or "")
            if "出院记录" in record_type:
                cache["出院记录"].append(record)
            if record_type not in {"出院记录", "疾病诊断证明"}:
                cache["入院记录"].append(record)

        course_records = self.execute_query("病程文书合并")
        for record in course_records or []:
            record_type = str(record.get("RCD_TP_NM") or "")
            if "首次病程记录" in record_type:
                cache["首次病程记录"].append(record)
            if "医师查房记录" in record_type:
                cache["上级医生查房记录"].append(record)
            if "日常病程记录" in record_type:
                cache["日常病程记录"].append(record)
            if "化疗记录" in record_type:
                cache["化疗记录"].append(record)
            if record_type == "在院评估单":
                cache["在院评估单"].append(record)

        self._document_records_cache = cache
        return cache

    def execute_patient_basic_query(self):
        """护理模块已移除，仅保留其他模块依赖的基础字段。"""
        if self._patient_basic_records_cache is not None:
            return self._patient_basic_records_cache

        if "患者基础信息" in self._prefetched_module_records:
            self._patient_basic_records_cache = self._prefetched_module_records.get("患者基础信息", [])
            print(f"批量预取缓存命中[患者基础信息]: {len(self._patient_basic_records_cache)} 条")
            return self._patient_basic_records_cache

        started_at = time.perf_counter()
        mdc_condition = f"AND MDC_ORG_CD = '{self.mdc_org_cd}'" if self.mdc_org_cd else ""
        query = f"""
                SELECT DSCG_DPT_NM, ADMN_DPT_NM, ADMN_DT_TM, DSCG_DT_TM, NM, GDR_NM, AGE, AGE_UNT, INHOS_NO, INVLD_FLG
                FROM ODS_FACT_MDC_RCD_HMPG
                WHERE INHOS_NO = '{self.inhos_no}' {mdc_condition}
                LIMIT 1;
            """
        try:
            with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(query)
                results = cursor.fetchall()
            print(f"SQL耗时[患者基础信息]: {time.perf_counter() - started_at:.3f}s，原始返回 {len(results)} 条")
        except Exception as e:
            print(f"患者基础信息查询失败: {e}，耗时 {time.perf_counter() - started_at:.3f}s")
            self._patient_basic_records_cache = []
            return []

        valid_records = []
        for record in results or []:
            invld_value = record.get("INVLD_FLG")
            if invld_value == 1 or invld_value == "1" or invld_value == 1.0:
                continue
            valid_records.append({k: v for k, v in record.items() if k != "INVLD_FLG"})

        self._patient_basic_records_cache = valid_records
        return valid_records

    def execute_nursing_query(self):
        """执行护理记录的分表查询，处理表不存在的情况"""
        result = {}
        mdc_condition = f"AND MDC_ORG_CD = '{self.mdc_org_cd}'" if self.mdc_org_cd else ""

        # 查询主表FACT_MDC_RCD_HMPG (这个是必须的)
        try:
            main_query = f"""
                SELECT DSCG_DPT_NM, ADMN_DPT_NM, ADMN_DT_TM, DSCG_DT_TM, NM, GDR_NM, AGE, INHOS_NO, INVLD_FLG
                FROM ODS_FACT_MDC_RCD_HMPG
                WHERE INHOS_NO = '{self.inhos_no}' {mdc_condition};
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
                "name": "ODS_FACT_DSCG_RCD",
                "columns": ["ADMN_DIAG_WTM_DIAG_NM", "ADMN_DIAG_TCM_DSES_NM", "CDT_TNOVR_NM"],
                "query": f"""
                    SELECT
                        ADMN_DIAG_WTM_DIAG_NM as DSCG_ADMN_DIAG_WTM_DIAG_NM,
                        ADMN_DIAG_TCM_DSES_NM as DSCG_ADMN_DIAG_TCM_DSES_NM,
                        CDT_TNOVR_NM,
                        INHOS_NO as DSCG_INHOS_NO,
                        INVLD_FLG
                    FROM ODS_FACT_DSCG_RCD
                    WHERE INHOS_NO = '{self.inhos_no}' {mdc_condition};
                """
            },
            {
                "name": "ODS_FACT_TCM_MDC_RCD_HMPG",
                "columns": ["BED_NO"],
                "query": f"""
                    SELECT
                        BED_NO,
                        INHOS_NO as TCM_INHOS_NO,
                        INVLD_FLG
                    FROM ODS_FACT_TCM_MDC_RCD_HMPG
                    WHERE INHOS_NO = '{self.inhos_no}' {mdc_condition};
                """
            },
            {
                "name": "ODS_FACT_ADMN_MDC_HTR_RCD",
                "columns": ["HGT", "WGT", "BRF_DSES_HST", "TPR", "PLS_RATE", "BRTH_FRQ", "STLC_PRS", "DTLC_PRS"],
                "query": f"""
                    SELECT
                        HGT, WGT, BRF_DSES_HST, TPR, PLS_RATE, BRTH_FRQ, STLC_PRS, DTLC_PRS,
                        INHOS_NO as ADMN_INHOS_NO,
                        INVLD_FLG
                    FROM ODS_FACT_ADMN_MDC_HTR_RCD
                    WHERE INHOS_NO = '{self.inhos_no}' {mdc_condition};
                """
            },
            {
                "name": "ODS_FACT_DSCG_MDC_HTR_RCD",
                "columns": ["MAIN_TEST_RSLT", "LBRTR_EXAM_MAIN_CSTT", "ESPCL_EXAM", "PSTV_AXLR_EXAM_RSLT",
                            "OTHR_MDC_DSPST", "DSCG_CDT", "DIAG_TRTMT_PRCS_DSCPT", "DSCG_ODR"],
                "query": f"""
                    SELECT
                        MAIN_TEST_RSLT, LBRTR_EXAM_MAIN_CSTT, ESPCL_EXAM, PSTV_AXLR_EXAM_RSLT,
                        OTHR_MDC_DSPST, DSCG_CDT, DIAG_TRTMT_PRCS_DSCPT, DSCG_ODR,
                        INHOS_NO as DSCG_MDC_INHOS_NO,
                        INVLD_FLG
                    FROM ODS_FACT_DSCG_MDC_HTR_RCD
                    WHERE INHOS_NO = '{self.inhos_no}' {mdc_condition};
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
                modules = ["病理", "医嘱", "检查", "检验", "诊断", "诊断信息", "病案首页诊断信息", "病案首页手术信息", "病案首页", "手术记录", "在院评估单", "收费", "医保", "用药信息"]

            result = {}
            list_modules = ["病理", "医嘱", "检查", "检验", "诊断", "诊断信息", "病案首页诊断信息", "病案首页手术信息", "病案首页", "手术记录", "收费", "医保", "用药信息"]
            derive_medication_from_fee = "用药信息" in modules and "收费" in modules
            parallel_modules = [
                module for module in modules
                if module in list_modules
                and module not in self._prefetched_module_records
                and not (derive_medication_from_fee and module == "用药信息")
            ]
            serial_modules = [
                module for module in modules
                if module not in list_modules or module in self._prefetched_module_records
            ]
            raw_records_by_module = {}

            try:
                max_workers = int(os.environ.get("SQL_MAX_WORKERS", "3"))
            except ValueError:
                max_workers = 3
            max_workers = max(1, min(max_workers, len(parallel_modules) or 1))

            if parallel_modules and max_workers > 1:
                print(f"并行执行结构化SQL模块: {len(parallel_modules)} 个模块，线程数 {max_workers}")
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_module = {
                        executor.submit(self.execute_query_with_new_connection, module): module
                        for module in parallel_modules
                    }
                    for future in as_completed(future_to_module):
                        module = future_to_module[future]
                        try:
                            records = future.result()
                        except Exception as e:
                            print(f"并行模块处理失败[{module}]: {e}")
                            records = []
                        raw_records_by_module[module] = records
                        result[module] = self.converter.process_result(module, records) if records else []
            else:
                for module in parallel_modules:
                    records = self.execute_query(module)
                    raw_records_by_module[module] = records
                    result[module] = self.converter.process_result(module, records) if records else []

            for module in serial_modules:
                records = self.execute_query(module)
                raw_records_by_module[module] = records
                if module == "在院评估单":
                    result[module] = self.converter.process_assessment_form(records)
                else:
                    result[module] = self.converter.process_result(module, records) if records else []

            if derive_medication_from_fee:
                fee_records = raw_records_by_module.get("收费", [])
                medication_records = self._filter_medication_records_from_fee(fee_records)
                result["用药信息"] = self.converter.process_result("用药信息", medication_records) if medication_records else []

            return result

    def _filter_medication_records_from_fee(self, fee_records):
            drug_categories = {"中成药", "中草药", "西药"}
            medication_records = []
            for record in fee_records or []:
                fee_category = str(record.get("FEE_CGY_NM") or "").strip()
                return_flag = record.get("CHRG_RTRN_FLG")
                is_returned = return_flag == 1 or return_flag == 1.0 or str(return_flag).strip() == "1"
                if fee_category in drug_categories and is_returned:
                    medication_records.append(record)
            return self._enrich_medication_records_with_drug_dim(medication_records)

    def _enrich_medication_records_with_drug_dim(self, medication_records):
            if not medication_records:
                return []

            pairs = sorted({
                (str(record.get("MDC_ORG_CD") or "").strip(), str(record.get("CHRG_ITM_CD") or "").strip())
                for record in medication_records
                if str(record.get("MDC_ORG_CD") or "").strip() and str(record.get("CHRG_ITM_CD") or "").strip()
            })
            if not pairs:
                return medication_records

            placeholders = ", ".join(["(%s, %s)"] * len(pairs))
            params = []
            for org_cd, drug_cd in pairs:
                params.extend([org_cd, drug_cd])

            query = f"""
                SELECT MDC_ORG_CD, DRG_CD,
                       MAX(DRG_CMN_NM) AS DRG_CMN_NM,
                       MAX(MDCR_DRG_CD_CTRY) AS MDCR_DRG_CD_CTRY
                FROM ODS_DIM_DRG_INFMT
                WHERE (MDC_ORG_CD, DRG_CD) IN ({placeholders})
                GROUP BY MDC_ORG_CD, DRG_CD
            """
            try:
                with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
                    cursor.execute(query, params)
                    dim_rows = cursor.fetchall()
            except Exception as e:
                print(f"药品维表补充查询失败: {e}")
                return medication_records

            dim_map = {
                (str(row.get("MDC_ORG_CD") or "").strip(), str(row.get("DRG_CD") or "").strip()): row
                for row in dim_rows or []
            }
            for record in medication_records:
                key = (str(record.get("MDC_ORG_CD") or "").strip(), str(record.get("CHRG_ITM_CD") or "").strip())
                dim_row = dim_map.get(key)
                if dim_row:
                    record["DRG_CMN_NM"] = dim_row.get("DRG_CMN_NM")
                    record["MDCR_DRG_CD_CTRY"] = dim_row.get("MDCR_DRG_CD_CTRY")
            return medication_records

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
        return llm_extractors.extract_admission_record(self, records, multi_model_api)

    def extract_first_course_record(self, records):
        """使用大模型提取首次病程记录内容 - 专注于DCMT_CTT字段"""
        return llm_extractors.extract_first_course_record(self, records, multi_model_api)

    def extract_ward_round_records(self, records, physician_type):
        """
        Extract the first ward round record for a specific physician type

        Args:
            records: List of ward round records
            physician_type: "主治医师" or "主任医师"

        Returns:
            Dictionary with extracted information
        """
        return llm_extractors.extract_ward_round_records(self, records, physician_type, multi_model_api)

    def extract_discharge_record(self, records):
        """提取出院记录内容 - 直接提取出院诊断，其余字段仍使用大模型"""
        return llm_extractors.extract_discharge_record(self, records, multi_model_api)

    def extract_daily_course_records(self, records):
        """
        使用大模型提取多条日常病程记录内容

        Args:
            records: 从数据库查询到的日常病程记录列表

        Returns:
            列表，每个元素是包含时间和文本的字典
        """
        return llm_extractors.extract_daily_course_records(self, records, multi_model_api)

    def extract_chemotherapy_records(self, records):
        """
        使用大模型提取多条化疗记录内容

        Args:
            records: 从数据库查询到的化疗记录列表

        Returns:
            列表，每个元素是包含化疗记录信息的字典
        """
        return llm_extractors.extract_chemotherapy_records(self, records, multi_model_api)

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

    def process_all_and_export(self, output_file=None, existing_icd10=None, output_root=None):
        # 定义应包含的所有模块
        required_modules = ["病理", "医嘱", "检查", "检验", "诊断", "手术记录", "收费", "医保", "治疗用药", "手术用药"]
        required_documents = ["入院记录", "首次病程记录", "主治医师首次查房记录", "主任医师首次查房记录", "日常病程记录", "化疗记录", "出院记录"]
        empty_modules = []
        result = {"病历文书": [], "主要ICD10编码": {}}
        print("获取所有需要AI处理的文档原始数据...")
        document_records = self.execute_document_queries()
        admission_records = document_records.get("入院记录", [])
        first_course_records = document_records.get("首次病程记录", [])
        attending_round_records = document_records.get("上级医生查房记录", [])
        chief_round_records = attending_round_records.copy() if attending_round_records else []
        daily_records = document_records.get("日常病程记录", [])
        chemotherapy_records = document_records.get("化疗记录", [])
        discharge_records = document_records.get("出院记录", [])

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
            "化疗记录": (chemotherapy_records, self.extract_chemotherapy_records)
            # 移除手术记录的AI处理，只使用结构化数据
        }

        # 执行并行处理
        all_parallel_results = self.process_documents_parallel_wrapper(all_parallel_tasks)

        extracted_admission = all_parallel_results.get("入院记录", {})
        if not isinstance(extracted_admission, dict):
            extracted_admission = {}
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

        admission_main_diag_records = self.execute_query("入院主要诊断")
        admission_main_diag_code = ""
        admission_main_diag_name = ""
        if admission_main_diag_records:
            first_record = admission_main_diag_records[0] if isinstance(admission_main_diag_records, list) else {}
            if isinstance(first_record, dict):
                admission_main_diag_code = first_record.get("DIAG_ICD10_CD") or ""
                admission_main_diag_name = first_record.get("DIAG_ICD10_NM") or ""

        result["入院记录"] = {
            "创建时间": record_time,
            "入院主要诊断编码": admission_main_diag_code,
            "入院主要诊断名称": admission_main_diag_name,
            **{
                k: v
                for k, v in extracted_admission.items()
                if k not in ["时间", "创建时间", "内容缺失", "原因"]
            }
        }

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

        discharge_extract = all_parallel_results.get("出院记录", {})

        if existing_icd10:
            print("使用已有的ICD10匹配结果")
            main_icd10 = existing_icd10
        else:
            main_icd10 = self.get_main_icd10_from_home_page()
            print(f"主要ICD10编码来自病案首页: {main_icd10['code']} | {main_icd10['name']} (匹配度: {main_icd10['match_rate']}%)")

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
        if not result["日常病程记录"]:
            result["日常病程记录"] = [{"创建时间": "xxx", "文本": "xxx"}]

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
        if not result["化疗记录"]:
            result["化疗记录"] = [{
                "创建时间": "xxx",
                "化疗药品名称": "xxx",
                "药品剂量": "xxx",
                "化疗方案": "xxx",
                "化疗周期": "xxx",
                "化疗日期": "xxx",
                "化疗反应": "xxx",
                "化疗效果": "xxx",
                "备注": "xxx"
            }]

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

        discharge_main_diag_records = self.execute_query("出院主要诊断")
        discharge_main_diag_code = ""
        discharge_main_diag_name = ""
        if discharge_main_diag_records:
            first_record = discharge_main_diag_records[0] if isinstance(discharge_main_diag_records, list) else {}
            if isinstance(first_record, dict):
                discharge_main_diag_code = first_record.get("DIAG_ICD10_CD") or ""
                discharge_main_diag_name = first_record.get("DIAG_ICD10_NM") or ""

        result["出院记录"] = {
            "创建时间": record_time,
            "出院主要诊断编码": discharge_main_diag_code,
            "出院主要诊断名称": discharge_main_diag_name,
            **{k: v for k, v in discharge_extract.items() if k not in ["时间", "创建时间"]}
        }

        # 手术记录现在通过modules_to_process统一处理结构化数据，不再需要特殊处理AI结果

        # 处理在院评估单（特殊）
        records = document_records.get("在院评估单", [])
        result["病历文书"].append({"文书名": "在院评估单", "时间": "xxx", "内容": {}})

        # ======================================================
        # 第5步：处理需要字段映射的模块
        # ======================================================
        print("处理结构化模块数据...")
        modules_to_process = ["病理", "医嘱", "检查", "检验", "诊断信息", "病案首页诊断信息", "病案首页手术信息", "病案首页", "手术记录", "收费", "医保", "用药信息"]
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
        patient_basic_records = self.execute_patient_basic_query()

        patient_gender = "xxx"
        patient_age = "xxx"
        patient_AGE_UNT = "xxx"  # 添加默认值，避免UnboundLocalError

        if patient_basic_records and isinstance(patient_basic_records, list) and len(patient_basic_records) > 0:
            first_basic_record = patient_basic_records[0]
            patient_gender = self.converter.format_value(first_basic_record.get("GDR_NM") or first_basic_record.get("M_GDR_NM"))
            patient_age = self.converter.format_value(first_basic_record.get("AGE") or first_basic_record.get("M_AGE"))
            patient_AGE_UNT = self.converter.format_value(first_basic_record.get("AGE_UNT") or first_basic_record.get("M_AGE_UNT"))


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
            if isinstance(data, list) and len(data) == 0:
                placeholder = self.converter.build_default_record_for_module(module)
                if placeholder:
                    data = [placeholder]
            new_module_name = rename_map.get(module, module)
            result[new_module_name] = data

        # 添加最终处理好的医保信息
        result["医保信息"] = processed_insurance_data # 使用新键名

        # 新增：提取基本信息模块
        basic_info = {
            "住院流水号": self.inhos_no,
            "入院日期": "xxx",
            "出院日期": "xxx",
            "病种名称": "其他病种"
        }
        icd10_code = ""
        icd9_code = ""
        age_value = None

        # 护理模块已移除，这里复用轻量基础信息查询中的入院/出院日期。
        if patient_basic_records:
            # 假设基本信息在第一条记录中
            first_record = patient_basic_records[0]
            basic_info["入院日期"] = self.converter.format_date(first_record.get("ADMN_DT_TM"))
            basic_info["出院日期"] = self.converter.format_date(first_record.get("DSCG_DT_TM"))
            # 住院流水号已经通过self.inhos_no获取，更可靠

            home_main_diag = modules_result.get("病案首页诊断信息") or []
            if isinstance(home_main_diag, list) and len(home_main_diag) > 0 and isinstance(home_main_diag[0], dict):
                icd10_code = home_main_diag[0].get("出院主要诊断编码") or home_main_diag[0].get("DIAG_CD") or ""
            surgery_records = modules_result.get("手术记录") or []
            if isinstance(surgery_records, list):
                for surgery_record in surgery_records:
                    if not isinstance(surgery_record, dict):
                        continue
                    main_flag = surgery_record.get("主手术标识") or surgery_record.get("MAIN_OPRT_FLG")
                    if main_flag == 1 or main_flag == 1.0 or str(main_flag).strip() == "1":
                        icd9_code = surgery_record.get("手术编码") or surgery_record.get("OPRT_CD") or ""
                        break
            if not icd9_code:
                main_icd9 = self.get_main_icd9_from_oprt_exec()
                icd9_code = main_icd9.get("code") if isinstance(main_icd9, dict) else ""
            age_value = first_record.get("AGE")

        if not icd10_code and isinstance(existing_icd10, dict):
            icd10_code = existing_icd10.get("code") or ""

        secondary_icd10_codes = []
        for diag_record in modules_result.get("诊断信息") or []:
            if not isinstance(diag_record, dict):
                continue
            main_flag = diag_record.get("主诊断标识") or diag_record.get("MAIN_DIAG_FLG")
            if main_flag == 1 or main_flag == 1.0 or str(main_flag).strip() == "1":
                continue
            secondary_code = diag_record.get("诊断编码") or diag_record.get("ICD编码") or diag_record.get("DIAG_CD")
            if secondary_code:
                secondary_icd10_codes.append(secondary_code)

        disease_matches = self.match_diseases_by_codes(
            icd10_code,
            age_value,
            secondary_icd10_codes=secondary_icd10_codes,
            icd9_code=icd9_code,
        )
        if not disease_matches:
            disease_matches = [{"type": "UNMATCHED", "disease": "其他病种"}]
        basic_info["病种名称"] = "、".join(match["disease"] for match in disease_matches)
        basic_info["主要ICD10编码"] = icd10_code or "xxx"
        basic_info["主要ICD9编码"] = icd9_code or "xxx"

        result["基本信息"] = basic_info
        department_name = self.get_department_folder_name(patient_basic_records, modules_result, result)
        result["专科名称"] = department_name
        result["专科名"] = department_name

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

                if output_root:
                    output_file_name = os.path.basename(output_file)
                    saved_files = self.save_result_by_disease_structure(
                        result,
                        output_root,
                        output_file_name,
                        disease_matches,
                        department_name,
                    )
                    result["_saved_files"] = saved_files
                else:
                    # 然后再导出
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(result, f, ensure_ascii=False, indent=2)
                    print(f"数据已导出到: {output_file}")
            except Exception as e:
                print(f"导出JSON失败: {e}")

        return result


def main():
    """主函数 - 支持从CSV文件或手动输入处理住院号"""
    verbose = os.environ.get("VERBOSE", "").strip().lower() in {"1", "true", "yes", "y"}

    def info(message: str):
        print(message)

    def debug(message: str):
        if verbose:
            print(message)

    info("请选择处理方式:")
    info("1. 从CSV文件读取住院号")
    info("2. 手动输入住院号")
    choice_mode = input("请输入选择 (1 或 2): ").strip()

    if choice_mode == '2':
        info("\n--- 手动输入住院号处理模式 ---")
        manual_output_dir = FIXED_OUTPUT_DIR
        try:
            os.makedirs(manual_output_dir, exist_ok=True)
            debug(f"手动输入处理结果将保存到: {manual_output_dir}")
        except OSError as e:
            info(f"创建结果目录失败: {e}。程序退出。")
            return

        # 输入医疗机构代码
        mdc_org_cd_input = input("请输入医疗机构代码(MDC_ORG_CD): ").strip()
        if not mdc_org_cd_input:
            info("未输入医疗机构代码，程序退出。")
            return
        info(f"医疗机构代码: {mdc_org_cd_input}")

        inhos_nos_input_str = input("请输入一个或多个住院号 (用逗号分隔): ").strip()
        if not inhos_nos_input_str:
            info("未输入任何住院号。程序退出。")
            return

        manual_inhos_nos = [no.strip() for no in inhos_nos_input_str.split(',') if no.strip()]
        if not manual_inhos_nos:
            info("输入的住院号无效。程序退出。")
            return

        info(f"\n将处理 {len(manual_inhos_nos)} 个住院号，医疗机构代码: {mdc_org_cd_input}")
        if verbose:
            for i, inhos_no_val in enumerate(manual_inhos_nos, 1):
                info(f"{i}. {inhos_no_val}")

        confirm_manual_processing = input("确认处理这些记录吗? (y/n): ").lower()
        if confirm_manual_processing != 'y':
            info("操作已取消，程序结束。")
            return

        successfully_processed_manual = []
        failed_to_process_manual = []

        if len(manual_inhos_nos) > 1:
            prefetch_choice = input("是否启用批量SQL预取缓存？适合一次处理多个住院号，可减少重复全表扫描 (y/n，默认n): ").strip().lower()
            if prefetch_choice == "y":
                prefetch_batch_size_str = input("请输入每批预取住院号数量(默认50，建议20-100): ").strip()
                try:
                    prefetch_batch_size = int(prefetch_batch_size_str or "50")
                except ValueError:
                    prefetch_batch_size = 50
                MedicalDataProcessor.batch_prefetch_records(manual_inhos_nos, batch_size=prefetch_batch_size, mdc_org_cd=mdc_org_cd_input)
            else:
                MedicalDataProcessor.clear_batch_prefetch_cache()
        else:
            MedicalDataProcessor.clear_batch_prefetch_cache()

        for idx, current_inhos_no in enumerate(manual_inhos_nos):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            info(f"\n[{idx + 1}/{len(manual_inhos_nos)}] 处理住院号: {current_inhos_no}")

            processor = None
            try:
                processor = MedicalDataProcessor(inhos_no=current_inhos_no, mdc_org_cd=mdc_org_cd_input)
                output_file_name = f"patient_{current_inhos_no}_{timestamp}.json"
                current_output_file_path = os.path.join(manual_output_dir, output_file_name)

                # 对于手动输入，我们不进行来自CSV的ICD10范围预检查
                # process_all_and_export 会自行提取和处理ICD10信息
                result_data = processor.process_all_and_export(output_file=current_output_file_path, output_root=manual_output_dir)

                if result_data and not result_data.get("提前终止"): # 检查是否提前终止
                    info(f"完成: {current_inhos_no}")
                    saved_files = result_data.get("_saved_files") or [current_output_file_path]
                    debug(f"导出文件: {saved_files}")
                    successfully_processed_manual.append(current_inhos_no)

                    # 删除同住院号的旧文件
                    delete_old_files_for_inhos_no_recursive(manual_output_dir, current_inhos_no, saved_files)
                elif result_data and result_data.get("提前终止"):
                    info(f"提前终止: {current_inhos_no} | {result_data.get('终止原因', '未知原因')}")
                    failed_to_process_manual.append(current_inhos_no)
                else: # 其他类型的处理失败
                    info(f"失败: {current_inhos_no}")
                    failed_to_process_manual.append(current_inhos_no)


            except Exception as e_proc:
                info(f"错误: {current_inhos_no} | {e_proc}")
                import traceback
                traceback.print_exc()
                failed_to_process_manual.append(current_inhos_no)
            finally:
                if processor and hasattr(processor, 'connection') and processor.connection:
                    try:
                        processor.connection.close()
                        debug(f"数据库连接已关闭: {current_inhos_no}")
                    except Exception as e_close_proc:
                        info(f"关闭数据库连接出错: {current_inhos_no} | {e_close_proc}")

        info(f"\n处理完成: 成功 {len(successfully_processed_manual)}，失败/终止 {len(failed_to_process_manual)}。")
        if verbose:
            if successfully_processed_manual:
                info("成功住院号:")
                for no in successfully_processed_manual:
                    info(f"- {no}")
            if failed_to_process_manual:
                info("失败/终止住院号:")
                for no in failed_to_process_manual:
                    info(f"- {no}")

        total_json_files_in_manual_dir = 0
        if os.path.exists(manual_output_dir):
            total_json_files_in_manual_dir = len(glob.glob(os.path.join(manual_output_dir, "**", "patient_*.json"), recursive=True))
        debug(f"\n当前目录 '{manual_output_dir}' 中共有 {total_json_files_in_manual_dir} 个病历JSON文件。")


    elif choice_mode == '1':
        info("\n--- 从CSV文件处理模式 ---")
        source_base_dir = "/home/user/bingli1"
        disease_folder_names = []

        if os.path.exists(source_base_dir) and os.path.isdir(source_base_dir):
            for item in os.listdir(source_base_dir):
                item_path = os.path.join(source_base_dir, item)
                if os.path.isdir(item_path):
                    disease_folder_names.append(item)

        if not disease_folder_names:
            # 在CSV模式下，如果初始的疾病文件夹列表为空，则直接提示并退出该模式
            info(f"在源路径 {source_base_dir} 未找到任何疾病文件夹。")
            # 可以选择在这里调用 main() 重新开始，或者直接退出
            return


        info("\n请选择疾病文件夹:")
        for i, dir_name in enumerate(disease_folder_names, 1):
            info(f"{i}. {dir_name}")

        selected_disease_name_for_output = ""
        original_csv_dir_path = ""

        try:
            choice_str = input(f"请输入文件夹编号(1-{len(disease_folder_names)}): ")
            if not choice_str.isdigit():
                info("输入无效，必须是数字。程序结束。")
                return
            choice = int(choice_str)
            if not (1 <= choice <= len(disease_folder_names)):
                info("输入无效的编号，程序结束。")
                return

            selected_disease_name_for_output = disease_folder_names[choice - 1]
            original_csv_dir_path = os.path.join(source_base_dir, selected_disease_name_for_output)

        except ValueError:
            print("输入无效，必须输入数字，程序结束。")
            return
        except Exception as e:
            print(f"选择疾病文件夹时发生错误: {e}")
            return

        final_json_output_dir = FIXED_OUTPUT_DIR
        try:
            os.makedirs(final_json_output_dir, exist_ok=True)
            debug(f"JSON输出目录: {final_json_output_dir}")
        except OSError as e:
            info(f"创建输出目录失败: {e}。")
            return

        csv_files_in_source_dir = []
        if os.path.exists(original_csv_dir_path) and os.path.isdir(original_csv_dir_path):
            for file_name in os.listdir(original_csv_dir_path):
                if file_name.endswith('.csv'):
                    csv_files_in_source_dir.append(file_name)

        if not csv_files_in_source_dir:
            info(f"在源路径 {original_csv_dir_path} 中未找到任何CSV文件。")
            return

        info(f"\n找到以下CSV文件:")
        for i, csv_name in enumerate(csv_files_in_source_dir, 1):
            info(f"{i}. {csv_name}")

        selected_csv_full_path = ""
        selected_csv_name_only = ""
        try:
            csv_choice_str = input(f"请输入CSV文件编号(1-{len(csv_files_in_source_dir)}): ")
            if not csv_choice_str.isdigit():
                info("输入无效，必须是数字。程序结束。")
                return
            csv_choice = int(csv_choice_str)
            if not (1 <= csv_choice <= len(csv_files_in_source_dir)):
                info("输入无效的编号，程序结束。")
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
                info(f"ICD10范围: {icd10_range}")

            try:
                df = pd.read_csv(selected_csv_full_path, skiprows=1, header=None, names=['INHOS_NO_RAW'], dtype=str, skip_blank_lines=True)
                if 'INHOS_NO_RAW' in df.columns:
                    df.dropna(subset=['INHOS_NO_RAW'], inplace=True)
                    df['INHOS_NO'] = df['INHOS_NO_RAW'].astype(str).str.strip()
                    df = df[df['INHOS_NO'] != '']
                else: # CSV可能只有一行（表头）或为空
                    df = pd.DataFrame(columns=['INHOS_NO'])

            except pd.errors.EmptyDataError:
                info(f"CSV文件 {selected_csv_name_only} (跳过首行后) 为空或格式不正确。")
                df = pd.DataFrame(columns=['INHOS_NO']) # 创建一个空的DataFrame以避免后续错误


            if 'INHOS_NO' not in df.columns or df.empty:
                info(f"CSV文件 {selected_csv_name_only} 未能解析出 INHOS_NO 或数据为空。")
                # 即使为空，也允许继续，以便用户可以手动编辑空的CSV或了解情况
                if df.empty:
                    info("CSV文件内容为空（除表头外）。")


            total_records = len(df)
            info(f"\nCSV住院号数量: {total_records}")
            if total_records == 0:
                info("CSV文件中没有可处理的住院号。")
                # 不直接退出，允许后续的手动编辑CSV流程

            process_count_str = input(f"请输入要处理的记录数量(默认为20, 输入 'all' 处理全部, 输入0跳过处理进入CSV编辑): ").strip().lower()

            if process_count_str == '0':
                process_count = 0
                info("跳过本轮处理。")
            elif process_count_str == 'all':
                process_count = total_records
            else:
                try:
                    process_count = int(process_count_str or "20")
                except ValueError:
                    info("处理数量输入无效，将使用默认值20。")
                    process_count = 20

            final_inhos_to_process = []
            if process_count > 0 and total_records > 0:
                process_count = min(process_count, total_records)
                batch_to_process_df = df.head(process_count)
                inhos_nos_from_csv = batch_to_process_df['INHOS_NO'].tolist()

                processed_inhos_in_output_dir = set()
                if os.path.exists(final_json_output_dir):
                    for file in glob.glob(os.path.join(final_json_output_dir, "**", "patient_*.json"), recursive=True):
                        match = re.search(r'patient_([A-Za-z0-9]+)_\d{8}_\d{6}\.json', os.path.basename(file))
                        if match:
                            processed_inhos_in_output_dir.add(match.group(1))
                debug(f"输出目录已处理住院号数量: {len(processed_inhos_in_output_dir)}")


                seen_in_this_batch = set()
                for inhos_no_item in inhos_nos_from_csv:
                    clean_inhos_no = str(inhos_no_item).strip()
                    if clean_inhos_no and clean_inhos_no not in processed_inhos_in_output_dir:
                        if clean_inhos_no not in seen_in_this_batch:
                            final_inhos_to_process.append(clean_inhos_no)
                            seen_in_this_batch.add(clean_inhos_no)
                        else:
                            debug(f"住院号重复(本批次仅处理一次): {clean_inhos_no}")
                    elif clean_inhos_no in processed_inhos_in_output_dir:
                         debug(f"已处理过，跳过: {clean_inhos_no}")
                    elif not clean_inhos_no:
                         debug("发现空住院号条目，已跳过。")

                if not final_inhos_to_process:
                    info("本轮无需要处理的住院号。")
                else:
                    info(f"\n将处理 {len(final_inhos_to_process)} 个住院号。")
                    if verbose:
                        for i, inhos_no_val in enumerate(final_inhos_to_process, 1):
                            info(f"{i}. {inhos_no_val}")

                    # 输入医疗机构代码
                    mdc_org_cd_csv = input("请输入医疗机构代码(MDC_ORG_CD): ").strip()
                    if not mdc_org_cd_csv:
                        info("未输入医疗机构代码，程序退出。")
                        return
                    info(f"医疗机构代码: {mdc_org_cd_csv}")

                    confirm_processing = input("确认处理这些记录吗? (y/n): ").lower()
                    if confirm_processing != 'y':
                        info("操作已取消。")
                        final_inhos_to_process = [] # 清空列表，不进行处理

            elif process_count == 0: # 用户选择不处理
                 final_inhos_to_process = []
            else: # total_records is 0
                 final_inhos_to_process = []


            matched_records_icd10 = []
            unmatched_records_icd10 = []
            successfully_generated_files = []

            if final_inhos_to_process: # 仅当有待处理记录时才进入循环
                use_batch_prefetch = False
                prefetch_choice = input("是否启用批量SQL预取缓存？适合一次处理多个住院号，可减少重复全表扫描 (y/n，默认n): ").strip().lower()
                if prefetch_choice == "y":
                    use_batch_prefetch = True
                    prefetch_batch_size_str = input("请输入每批预取住院号数量(默认50，建议20-100): ").strip()
                    try:
                        prefetch_batch_size = int(prefetch_batch_size_str or "50")
                    except ValueError:
                        prefetch_batch_size = 50
                    MedicalDataProcessor.batch_prefetch_records(final_inhos_to_process, batch_size=prefetch_batch_size, mdc_org_cd=mdc_org_cd_csv)
                else:
                    MedicalDataProcessor.clear_batch_prefetch_cache()

                for idx, current_inhos_no in enumerate(final_inhos_to_process):
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    info(f"\n[{idx + 1}/{len(final_inhos_to_process)}] 处理住院号: {current_inhos_no}")

                    processor = None
                    try:
                        processor = MedicalDataProcessor(inhos_no=current_inhos_no, mdc_org_cd=mdc_org_cd_csv)
                        main_icd10_info = processor.get_main_icd10_from_home_page()
                        if not main_icd10_info or str(main_icd10_info.get("code", "")).startswith("未找到"):
                            info(f"跳过(未找到主诊断ICD10): {current_inhos_no}")
                            unmatched_records_icd10.append(current_inhos_no)
                            continue


                        is_in_icd10_range, matched_range_part = processor.is_icd10_in_range(main_icd10_info['code'], icd10_range)

                        if is_in_icd10_range:
                            debug(f"ICD10命中: {current_inhos_no} | {main_icd10_info['code']} | {matched_range_part}")

                            output_file_name = f"patient_{current_inhos_no}_{timestamp}.json"
                            current_output_file_path = os.path.join(final_json_output_dir, output_file_name)

                            result_data = processor.process_all_and_export(output_file=current_output_file_path, existing_icd10=main_icd10_info, output_root=final_json_output_dir)
                            if result_data and not result_data.get("提前终止"):
                                info(f"完成: {current_inhos_no}")
                                saved_files = result_data.get("_saved_files") or [current_output_file_path]
                                debug(f"导出文件: {saved_files}")
                                successfully_generated_files.extend(saved_files)
                                matched_records_icd10.append(current_inhos_no) # 只有成功导出才加入此列表

                                # 删除同住院号的旧文件
                                delete_old_files_for_inhos_no_recursive(final_json_output_dir, current_inhos_no, saved_files)
                            elif result_data and result_data.get("提前终止"):
                                info(f"提前终止: {current_inhos_no} | {result_data.get('终止原因', '未知原因')}")
                                unmatched_records_icd10.append(current_inhos_no) # 即使在范围内，但处理终止
                            else:
                                info(f"失败: {current_inhos_no}")
                                unmatched_records_icd10.append(current_inhos_no)

                        else:
                            debug(f"ICD10未命中: {current_inhos_no} | {main_icd10_info['code']}")
                            unmatched_records_icd10.append(current_inhos_no)

                    except Exception as e_proc:
                        info(f"错误: {current_inhos_no} | {e_proc}")
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
                                info(f"关闭数据库连接出错: {current_inhos_no} | {e_close_proc}")

# --- CSV处理模式的汇总和CSV更新 ---
            info(f"\nCSV处理完成汇总:")
            if final_inhos_to_process: # 检查本轮是否有计划处理的住院号
                 info(f"- 计划处理: {len(final_inhos_to_process)}")
                 info(f"- 成功导出: {len(matched_records_icd10)}")
                 info(f"- 未导出/不符合: {len(unmatched_records_icd10)}")
                 if verbose:
                     if matched_records_icd10:
                         info("成功住院号:")
                         for inhos_no_val in matched_records_icd10:
                             info(f"- {inhos_no_val}")
                     if unmatched_records_icd10:
                         info("未导出/不符合住院号:")
                         for inhos_no_val in unmatched_records_icd10:
                             info(f"- {inhos_no_val}")
            else:
                info("- 本轮未处理任何住院号。")

            if verbose and successfully_generated_files:
                info(f"\n成功生成的JSON文件 ({len(successfully_generated_files)} 个):")
                for file_p in successfully_generated_files:
                    info(f"- {file_p}")

            total_json_files_in_output = 0
            if os.path.exists(final_json_output_dir):
                total_json_files_in_output = len(glob.glob(os.path.join(final_json_output_dir, "**", "patient_*.json"), recursive=True))
            debug(f"\n当前输出根目录 '{final_json_output_dir}' 中共有 {total_json_files_in_output} 个病历JSON文件。")

            # 自动更新CSV文件：移除本次所有尝试处理过的住院号
            # 修改开始
            if final_inhos_to_process: # 只要本轮有计划处理的住院号，就尝试更新CSV
                info(f"\n更新CSV: 移除本轮尝试处理的 {len(final_inhos_to_process)} 条住院号...")
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

                    info(f"更新完成: 剩余 {len(new_df_for_csv)} 条住院号。")
                    if len(new_df_for_csv) == 0:
                        info("CSV中已无待处理住院号。")

                except Exception as e_csv_write:
                    info(f"自动更新CSV文件出错: {e_csv_write}")
            else:
                debug(f"\n本轮没有计划处理的住院号，CSV文件 '{selected_csv_name_only}' 未被修改。")
            # 修改结束

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
        info("无效的选择。程序退出。")

if __name__ == "__main__":
    main()
    # print("脚本执行完毕.")
