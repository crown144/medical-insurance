import json
import re
from datetime import datetime


def _split_text_for_llm(text: str, *, max_chars: int, overlap: int) -> list[str]:
    if not text:
        return [""]
    text = str(text).replace("\r\n", "\n").replace("\r", "\n")
    if len(text) <= max_chars:
        return [text]

    heading_pattern = re.compile(
        r"(?m)^(?:\s*)(主诉|现病史|既往史|个人史|婚育史|月经史|家族史|体格检查|专科情况|辅助检查|初步诊断|更正诊断|FIGO分期|TNM分期|其他肿瘤分期|主治医师48小时诊断|入院情况|诊疗经过|合并症|出院情况|出院医嘱|出院指导|入院诊断|出院诊断)\s*[：:]"
    )
    boundaries = [m.start() for m in heading_pattern.finditer(text)]
    boundaries = [b for b in boundaries if 0 <= b < len(text)]
    if boundaries and boundaries[0] != 0:
        boundaries = [0] + boundaries
    if not boundaries:
        boundaries = [0]
    boundaries = sorted(set(boundaries))
    boundaries.append(len(text))

    sections: list[str] = []
    for i in range(len(boundaries) - 1):
        s = text[boundaries[i] : boundaries[i + 1]]
        if s.strip():
            sections.append(s)

    chunks: list[str] = []
    current = ""
    for section in sections:
        if not current:
            current = section
            continue
        if len(current) + len(section) <= max_chars:
            current += section
        else:
            chunks.append(current)
            current = section
    if current:
        chunks.append(current)

    refined: list[str] = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            refined.append(chunk)
            continue
        start = 0
        step = max(1, max_chars - overlap)
        while start < len(chunk):
            end = min(len(chunk), start + max_chars)
            refined.append(chunk[start:end])
            if end >= len(chunk):
                break
            start += step

    return [c for c in refined if c.strip()]


def _parse_json_from_llm_response(response: str):
    if not response:
        return None
    json_start = response.find("{")
    json_end = response.rfind("}") + 1
    if json_start < 0 or json_end <= json_start:
        return None
    json_str = response[json_start:json_end]
    json_str = json_str.replace("'", '"').replace("\n", " ")

    try:
        return json.loads(json_str)
    except Exception:
        try:
            json_str = re.sub(r"([{,])\s*([a-zA-Z0-9_\u4e00-\u9fa5]+)\s*:", r'\1"\2":', json_str)
            json_str = re.sub(
                r':\s*([^",\{\}\[\]\d][^",\{\}\[\]]*[^",\{\}\[\]\d])\s*([,\}])',
                r':"\1"\2',
                json_str,
            )
            return json.loads(json_str)
        except Exception:
            return None


def _pick_first_meaningful(values, *, empty_ok: bool):
    for v in values:
        if v is None:
            continue
        s = str(v).strip()
        if not s:
            continue
        if s == "文本中未提及该内容":
            continue
        return s
    return "" if empty_ok else "文本中未提及该内容"


def extract_admission_record(self, records, multi_model_api):
    """使用大模型提取入院记录内容，并判断内容是否完整"""
    default_result = {
        "创建时间": "xxx",
        "文档内容": "",
        "入院时间": "",
        "记录时间": "",
        "KPS评分": "",
        "ECOG_PS评分": "",
        "FIGO分期评分": "",
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
        "FIGO分期评分": "文本中未提及该内容",
        "KPS评分": "文本中未提及该内容",
        "ECOG_PS评分": "文本中未提及该内容",
        "TNM分期": "文本中未提及该内容",
        "其他肿瘤分期": "文本中未提及该内容",
        "主治医师48小时诊断": "文本中未提及该内容",
    }

    record_time = "xxx"

    if not records:
        print("警告: 未找到入院记录数据")
        default_result["创建时间"] = record_time
        return default_result
    dcmt_content = ""

    for record in records:
        if "INVLD_FLG" in record and record["INVLD_FLG"] == 1:
            print("入院记录INVLD_FLG=1，丢弃该记录")
            continue

        if "CRT_TM" in record and record["CRT_TM"]:
            record_time = self.converter.format_date(record["CRT_TM"])
            print(f"入院记录使用CRT_TM作为创建时间: {record_time}")
        elif "RCD_DT" in record and record["RCD_DT"]:
            record_time = self.converter.format_date(record["RCD_DT"])
            print(f"入院记录使用RCD_DT作为创建时间: {record_time}")

        if "DCMT_CTT" in record and record["DCMT_CTT"]:
            dcmt_content = record["DCMT_CTT"]
            print(f"成功提取DCMT_CTT内容，长度: {len(dcmt_content)}")
            break

    if not dcmt_content:
        print("错误: 未找到入院记录DCMT_CTT内容")
        default_result["创建时间"] = record_time
        return default_result

    def build_prompt(content: str, *, chunk_info: str) -> str:
        return f"""
请根据以下电子病历文本，提取入院记录的关键信息：

{content}

{chunk_info}

请从文本中提取以下入院记录的字段信息，提取的信息必须严格遵循原文，严禁擅自改写或添加任何额外的内容：
- 文档记录时间（文档中显示的时间，通常在文档开头或末尾，格式为年-月-日或年-月-日 时:分等。注意要找到哪个是入院记录，并定位它的时间）
- 入院时间（仅在文本明确提到时提取；未提及则留空字符串）
- 记录时间（仅在文本明确提到时提取；未提及则留空字符串。不要用创建时间/系统时间代替）
- KPS评分（仅在文本明确提到时提取；未提及则留空字符串）
- ECOG_PS评分（仅在文本明确提到时提取；未提及则留空字符串）
- FIGO分期评分（仅在文本明确提到时提取；未提及则留空字符串）
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
- FIGO分期评分
- KPS评分
- ECOG_PS评分
- TNM分期
- 其他肿瘤分期
- 主治医师48小时诊断

请按照以下格式返回JSON，不要添加任何其他说明：
{{
  "文档记录时间": "提取到的时间或'文本中未提及该内容'",
  "入院时间": "提取到的内容或空字符串",
  "记录时间": "提取到的内容或空字符串",
  "KPS评分": "提取到的内容或空字符串",
  "ECOG_PS评分": "提取到的内容或空字符串",
  "FIGO分期评分": "提取到的内容或空字符串",
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
  "FIGO分期评分": "文本中未提及该内容",
  "KPS评分": "文本中未提及该内容",
  "ECOG_PS评分": "文本中未提及该内容",
  "TNM分期": "文本内容或'文本中未提及该内容'",
  "其他肿瘤分期": "文本内容或'文本中未提及该内容'",
  "主治医师48小时诊断": "文本内容或'文本中未提及该内容'"
}}

特别注意：1、文本中若有与诊疗无关的个人敏感信息（包括：姓名，电话，邮箱，身份证号，地址等），将其隐藏为***，如文本“现住浙江省杭州市/生于浙江省杭州市”，将其隐藏为“现住***/生于***”，不要隐去性别、年龄等和诊疗有关的关键个人信息。
"""

    def parse_and_merge(extracted_dicts):
        result = default_result.copy()
        result["创建时间"] = record_time
        result["文档内容"] = dcmt_content
        doc_time = _pick_first_meaningful([d.get("文档记录时间") for d in extracted_dicts], empty_ok=False)
        result["时间"] = doc_time
        record_doc_time = _pick_first_meaningful([d.get("记录时间") for d in extracted_dicts], empty_ok=True)
        result["记录时间"] = record_doc_time

        empty_when_missing = {"入院时间", "KPS评分", "ECOG_PS评分", "FIGO分期评分"}
        for key in default_result:
            if key in {"创建时间", "记录时间"}:
                continue
            values = []
            for d in extracted_dicts:
                if key in d:
                    values.append(d.get(key))
            if not values:
                continue
            if key in empty_when_missing:
                picked = _pick_first_meaningful(values, empty_ok=True)
                result[key] = picked
            else:
                picked = _pick_first_meaningful(values, empty_ok=False)
                result[key] = picked

        return result

    extracted_dicts = []
    if len(dcmt_content) <= 12000:
        print("调用大模型提取入院记录信息...")
        response = multi_model_api.chat_method_for_module("入院记录", build_prompt(dcmt_content, chunk_info=""))
        parsed = _parse_json_from_llm_response(response)
        if parsed:
            extracted_dicts.append(parsed)
            return parse_and_merge(extracted_dicts)

    chunks = _split_text_for_llm(dcmt_content, max_chars=6000, overlap=400)
    print(f"入院记录文本过长，分段抽取: {len(chunks)} 段")
    for i, chunk in enumerate(chunks, start=1):
        chunk_info = f"这是长文本的第{i}/{len(chunks)}段。仅基于本段内容提取；本段未出现的字段按规则返回。"
        response = multi_model_api.chat_method_for_module("入院记录", build_prompt(chunk, chunk_info=chunk_info))
        parsed = _parse_json_from_llm_response(response)
        if parsed:
            extracted_dicts.append(parsed)

    if extracted_dicts:
        return parse_and_merge(extracted_dicts)

    default_result["创建时间"] = record_time
    return default_result


def extract_first_course_record(self, records, multi_model_api):
    """使用大模型提取首次病程记录内容 - 专注于DCMT_CTT字段"""
    default_result = {
        "创建时间": "xxx",
        "病例特点": "文本中未提及该内容",
        "初步诊断": "文本中未提及该内容",
        "诊断依据": "文本中未提及该内容",
        "鉴别诊断": "文本中未提及该内容",
        "拟诊讨论": "文本中未提及该内容",
        "诊疗计划": "文本中未提及该内容",
    }

    if not records:
        return default_result

    record_time = "xxx"
    dcmt_content = ""

    for record in records:
        if "INVLD_FLG" in record and record["INVLD_FLG"] == 1:
            print("首次病程记录INVLD_FLG=1，丢弃该记录")
            continue

        if "CRT_TM" in record and record["CRT_TM"]:
            record_time = self.converter.format_date(record["CRT_TM"])
            print(f"首次病程记录使用CRT_TM作为创建时间: {record_time}")
        elif "RCD_DT" in record and record["RCD_DT"]:
            record_time = self.converter.format_date(record["RCD_DT"])
            print(f"首次病程记录使用RCD_DT作为创建时间: {record_time}")

        if "DCMT_CTT" in record and record["DCMT_CTT"]:
            dcmt_content = record["DCMT_CTT"]
            print(f"成功提取首次病程记录DCMT_CTT内容，长度: {len(dcmt_content)}")
            break

    if not dcmt_content:
        print("未找到首次病程记录DCMT_CTT内容")
        default_result["时间"] = record_time
        return default_result

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
你必须严格按照以下格式返回JSON，不要添加任何其他说明，提取的信息必须严格遵循原文，严禁擅自改写或添加任何额外的内容：
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

    try:
        json_start = response.find("{")
        json_end = response.rfind("}") + 1

        if json_start >= 0 and json_end > json_start:
            json_str = response[json_start:json_end]
            print(f"提取到JSON字符串，长度: {len(json_str)}")

            json_str = json_str.replace("'", '"')
            json_str = json_str.replace("\n", " ")

            try:
                extracted_data = json.loads(json_str)
                print("成功解析首次病程记录JSON")

                result = default_result.copy()

                doc_time = extracted_data.get("文档记录时间", "文本中未提及该内容")
                if doc_time and doc_time != "文本中未提及该内容":
                    result["时间"] = doc_time
                else:
                    result["时间"] = "文本中未提及该内容"

                result["创建时间"] = record_time

                for key in extracted_data:
                    if key not in ["文档记录时间", "创建时间"] and key in result:
                        result[key] = extracted_data[key]

                return result
            except json.JSONDecodeError as e:
                pass

                try:
                    json_str = re.sub(r"([{,])\s*([a-zA-Z0-9_\u4e00-\u9fa5]+)\s*:", r'\1"\2":', json_str)
                    json_str = re.sub(
                        r':\s*([^",\{\}\[\]\d][^",\{\}\[\]]*[^",\{\}\[\]\d])\s*([,\}])',
                        r':"\1"\2',
                        json_str,
                    )

                    extracted_data = json.loads(json_str)
                    print("修复后成功解析首次病程记录JSON")

                    result = default_result.copy()

                    doc_time = extracted_data.get("文档记录时间", "文本中未提及该内容")
                    if doc_time and doc_time != "文本中未提及该内容":
                        result["时间"] = doc_time
                    else:
                        result["时间"] = record_time

                    for key in extracted_data:
                        if key != "文档记录时间" and key in result:
                            result[key] = extracted_data[key]

                    return result
                except Exception as e2:
                    pass
        else:
            print("未在首次病程记录响应中找到JSON结构")
    except Exception as e:
        print(f"处理首次病程记录大模型响应时出错: {e}")

    default_result["时间"] = record_time
    return default_result


def extract_ward_round_records(self, records, physician_type, multi_model_api):
    """
    Extract the first ward round record for a specific physician type

    Args:
        records: List of ward round records
        physician_type: "主治医师" or "主任医师"

    Returns:
        Dictionary with extracted information
    """
    if physician_type == "主治医师":
        default_result = {
            "时间": "xxx",
            "主治医生查房": "文本中未提及该内容",
            "诊断": "文本中未提及该内容",
            "诊断依据": "文本中未提及该内容",
            "鉴别诊断": "文本中未提及该内容",
            "诊疗计划": "文本中未提及该内容",
            "补充病史和体征": "文本中未提及该内容",
        }
    else:
        default_result = {
            "时间": "xxx",
            "主任医生查房": "文本中未提及该内容",
            "诊疗计划": "文本中未提及该内容",
            "注意事项": "文本中未提及该内容",
            "补充病史与体征": "文本中未提及该内容",
            "对病情的分析": "文本中未提及该内容",
            "诊疗意见": "文本中未提及该内容",
        }

    if not records:
        print(f"未找到{physician_type}查房记录")
        return default_result

    filtered_records = []
    from datetime import datetime
    import re

    for record in records:
        if "INVLD_FLG" in record and record["INVLD_FLG"] == 1:
            print(f"{physician_type}查房记录INVLD_FLG=1，丢弃该记录")
            continue

        if "DCMT_CTT" in record and record["DCMT_CTT"]:
            content = record["DCMT_CTT"]

            if physician_type in content and "查房记录" in content:
                date_match = re.search(r"(\d{4}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{1,2})", content)
                if date_match:
                    try:
                        doc_date = datetime.strptime(date_match.group(1), "%Y-%m-%d %H:%M")
                        print(f"从文档内容中提取到日期: {doc_date} - {physician_type}查房记录")
                        record["doc_date"] = doc_date
                        filtered_records.append(record)
                    except Exception as e:
                        print(f"日期解析错误: {e}")
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

    sorted_records = sorted(filtered_records, key=lambda x: x.get("doc_date", datetime.max))

    print(f"找到 {len(sorted_records)} 条{physician_type}查房记录")
    for idx, rec in enumerate(sorted_records[:3]):
        dt = rec.get("doc_date", "未知")
        content_preview = rec.get("DCMT_CTT", "")[:50] if rec.get("DCMT_CTT") else "无内容"
        print(f"Record {idx}: Date = {dt}, Content = {content_preview}...")

    if not sorted_records:
        print(f"排序后未找到{physician_type}查房记录")
        return default_result

    earliest_record = sorted_records[0]
    record_time = self.converter.format_date(earliest_record.get("doc_date", earliest_record.get("RCD_DT", "")))
    dcmt_content = earliest_record.get("DCMT_CTT", "")

    print(f"找到最早的{physician_type}查房记录，时间: {record_time}")
    print(f"内容预览: {dcmt_content[:100]}...")

    if not dcmt_content:
        print(f"最早的{physician_type}查房记录内容为空")
        default_result["时间"] = record_time
        return default_result

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

你必须严格按照以下格式返回JSON，不要添加任何其他说明，提取的信息必须严格遵循原文，严禁擅自改写或添加任何额外的内容：
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
    else:
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

你必须严格按照以下格式返回JSON，不要添加任何其他说明，提取的信息必须严格遵循原文，严禁擅自改写或添加任何额外的内容：
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
    response = multi_model_api.chat_method_for_module("上级医生查房记录", prompt)
    print(f"大模型响应长度: {len(response)}")

    try:
        json_start = response.find("{")
        json_end = response.rfind("}") + 1

        if json_start >= 0 and json_end > json_start:
            json_str = response[json_start:json_end]
            print(f"提取到JSON字符串，长度: {len(json_str)}")

            json_str = json_str.replace("'", '"')
            json_str = json_str.replace("\n", " ")

            try:
                extracted_data = json.loads(json_str)
                print(f"成功解析{physician_type}查房记录JSON")

                result = default_result.copy()

                doc_time = extracted_data.get("文档记录时间", "文本中未提及该内容")
                if doc_time and doc_time != "文本中未提及该内容":
                    result["时间"] = doc_time
                else:
                    result["时间"] = record_time

                for key in extracted_data:
                    if key != "文档记录时间" and key in result:
                        result[key] = extracted_data[key]

                return result
            except json.JSONDecodeError as e:
                pass

                try:
                    json_str = re.sub(r"([{,])\s*([a-zA-Z0-9_\u4e00-\u9fa5]+)\s*:", r'\1"\2":', json_str)
                    json_str = re.sub(
                        r':\s*([^",\{\}\[\]\d][^",\{\}\[\]]*[^",\{\}\[\]\d])\s*([,\}])',
                        r':"\1"\2',
                        json_str,
                    )

                    extracted_data = json.loads(json_str)
                    print(f"修复后成功解析{physician_type}查房记录JSON")

                    result = default_result.copy()

                    doc_time = extracted_data.get("文档记录时间", "文本中未提及该内容")
                    if doc_time and doc_time != "文本中未提及该内容":
                        result["时间"] = doc_time
                    else:
                        result["时间"] = record_time

                    for key in extracted_data:
                        if key != "文档记录时间" and key in result:
                            result[key] = extracted_data[key]

                    return result
                except Exception as e2:
                    pass
        else:
            print(f"未在{physician_type}查房记录响应中找到JSON结构")
    except Exception as e:
        print(f"处理{physician_type}查房记录大模型响应时出错: {e}")

    default_result["时间"] = record_time
    return default_result


def extract_discharge_record(self, records, multi_model_api):
    """提取出院记录内容 - 直接提取出院诊断，其余字段仍使用大模型"""
    default_result = {
        "创建时间": "xxx",
        "文档内容": "",
        "记录时间": "",
        "出院指导": "文本中未提及该内容",
        "入院日期": "文本中未提及该内容",
        "出院日期": "文本中未提及该内容",
        "入院诊断": "文本中未提及该内容",
        "出院诊断": "文本中未提及该内容",
        "入院情况": "文本中未提及该内容",
        "诊疗经过": "文本中未提及该内容",
        "合并症": "文本中未提及该内容",
        "出院情况": "文本中未提及该内容",
        "出院医嘱": "文本中未提及该内容",
    }

    if not records:
        return default_result

    record_time = "xxx"
    dcmt_content = ""

    for record in records:
        if "INVLD_FLG" in record and record["INVLD_FLG"] == 1:
            print("出院记录INVLD_FLG=1，丢弃该记录")
            continue

        if "CRT_TM" in record and record["CRT_TM"]:
            record_time = self.converter.format_date(record["CRT_TM"])
            print(f"出院记录使用CRT_TM作为创建时间: {record_time}")
        elif "RCD_DT" in record and record["RCD_DT"]:
            record_time = self.converter.format_date(record["RCD_DT"])
            print(f"出院记录使用RCD_DT作为创建时间: {record_time}")

        if "DCMT_CTT" in record and record["DCMT_CTT"]:
            dcmt_content = record["DCMT_CTT"]
            print(f"成功提取出院记录DCMT_CTT内容，长度: {len(dcmt_content)}")
            break

    if not dcmt_content:
        print("未找到出院记录DCMT_CTT内容")
        default_result["时间"] = record_time
        return default_result

    discharge_diagnosis = self.extract_discharge_diagnosis_first_item(dcmt_content)

    def build_prompt(content: str, *, chunk_info: str) -> str:
        return f"""
请根据以下电子病历文本（出院记录），提取除了出院诊断以外的关键信息：

{content}

{chunk_info}

请从文本中提取以下字段信息，提取的信息必须严格遵循原文，严禁擅自改写或添加任何额外的内容：
- 文档记录时间（文档中显示的时间，通常在文档末尾，格式为年-月-日或年-月-日 时:分等）
- 记录时间（仅在文本明确提到时提取；未提及则留空字符串。不要用创建时间/系统时间代替）
- 入院日期（患者入院的具体日期）
- 出院日期（患者出院的具体日期）
- 入院诊断（患者入院时的诊断结果）
- 入院情况（患者入院时的状态和症状）
- 诊疗经过（住院期间的治疗过程和检查）
- 合并症（患者同时存在的其他疾病）
- 出院情况（患者出院时的状态）
- 出院医嘱（出院后的用药、复诊等建议）
- 出院指导（对于患者出院医生给出的指导意见。不要将“出院医嘱/出院建议”自行改写成出院指导）

你必须严格按照以下格式返回JSON，不要添加任何其他说明：
{{
  "文档记录时间": "提取到的时间或'文本中未提及该内容'",
  "记录时间": "提取到的内容或空字符串",
  "入院日期": "文本内容或'文本中未提及该内容'",
  "出院日期": "文本内容或'文本中未提及该内容'",
  "入院诊断": "文本内容或'文本中未提及该内容'",
  "入院情况": "文本内容或'文本中未提及该内容'",
  "诊疗经过": "文本内容或'文本中未提及该内容'",
  "合并症": "文本内容或'文本中未提及该内容'",
  "出院情况": "文本内容或'文本中未提及该内容'",
  "出院医嘱": "文本内容或'文本中未提及该内容'",
  "出院指导": "文本内容或'文本中未提及该内容'"
}}

特别注意：1、仔细寻找文档中的任何日期时间信息，特别是文档末尾部分的时间戳。出院记录的文档时间通常会在医生签字附近。
2、除“记录时间”外，如果文本中未提及某个字段的内容，则该字段的值应为"文本中未提及该内容"；“记录时间”未提及则必须返回空字符串。
3、文本中若有与诊疗无关的个人敏感信息（包括：姓名，电话，邮箱，身份证号，地址等），将其隐藏为***，如文本“现住浙江省杭州市/生于浙江省杭州市”包含地址信息，将其隐藏为“现住***/生于***”，不要隐去性别、年龄等和诊疗有关的关键个人信息。
"""

    def parse_and_merge(extracted_dicts):
        result = default_result.copy()
        result["创建时间"] = record_time
        result["文档内容"] = dcmt_content
        doc_time = _pick_first_meaningful([d.get("文档记录时间") for d in extracted_dicts], empty_ok=False)
        result["时间"] = doc_time
        record_doc_time = _pick_first_meaningful([d.get("记录时间") for d in extracted_dicts], empty_ok=True)
        result["记录时间"] = record_doc_time

        for key in default_result:
            if key in {"创建时间", "记录时间", "出院诊断"}:
                continue
            values = []
            for d in extracted_dicts:
                if key in d:
                    values.append(d.get(key))
            if not values:
                continue
            result[key] = _pick_first_meaningful(values, empty_ok=False)

        result["出院诊断"] = discharge_diagnosis
        return result

    extracted_dicts = []
    if len(dcmt_content) <= 12000:
        print("调用大模型提取出院记录信息...")
        response = multi_model_api.chat_method_for_module("出院记录", build_prompt(dcmt_content, chunk_info=""))
        parsed = _parse_json_from_llm_response(response)
        if parsed:
            extracted_dicts.append(parsed)
            return parse_and_merge(extracted_dicts)

    chunks = _split_text_for_llm(dcmt_content, max_chars=6000, overlap=400)
    print(f"出院记录文本过长，分段抽取: {len(chunks)} 段")
    for i, chunk in enumerate(chunks, start=1):
        chunk_info = f"这是长文本的第{i}/{len(chunks)}段。仅基于本段内容提取；本段未出现的字段按规则返回。"
        response = multi_model_api.chat_method_for_module("出院记录", build_prompt(chunk, chunk_info=chunk_info))
        parsed = _parse_json_from_llm_response(response)
        if parsed:
            extracted_dicts.append(parsed)

    if extracted_dicts:
        return parse_and_merge(extracted_dicts)

    default_result["时间"] = record_time
    default_result["出院诊断"] = discharge_diagnosis
    default_result["文档内容"] = dcmt_content
    return default_result


def extract_daily_course_records(self, records, multi_model_api):
    """
    提取多条日常病程记录的创建时间与文本

    Args:
        records: 从数据库查询到的日常病程记录列表

    Returns:
        列表，每个元素是包含时间和文本的字典
    """
    if not records:
        return [{"时间": "xxx", "文本": "xxx"}]

    results = []

    for record in records:
        if "INVLD_FLG" in record and record["INVLD_FLG"] == 1:
            print("日常病程记录INVLD_FLG=1，丢弃该记录")
            continue

        if "DCMT_CTT" not in record or not record["DCMT_CTT"]:
            continue

        record_time = "xxx"
        dcmt_content = record["DCMT_CTT"]

        if "CRT_TM" in record and record["CRT_TM"]:
            record_time = self.converter.format_date(record["CRT_TM"])
            print(f"日常病程记录使用CRT_TM作为创建时间: {record_time}")
        elif "RCD_DT" in record and record["RCD_DT"]:
            record_time = self.converter.format_date(record["RCD_DT"])
            print(f"日常病程记录使用RCD_DT作为创建时间: {record_time}")

        results.append({"时间": record_time, "文本": dcmt_content})

    if not results:
        return [{"时间": "xxx", "文本": "xxx"}]

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
        except Exception:
            return datetime.max

    results.sort(key=lambda x: parse_date_safe(x["时间"]))

    return results


def extract_chemotherapy_records(self, records, multi_model_api):
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
        if "INVLD_FLG" in record and record["INVLD_FLG"] == 1:
            print("化疗记录INVLD_FLG=1，丢弃该记录")
            continue

        dcmt_content = record.get("DCMT_CTT", "")
        if not dcmt_content or dcmt_content.strip() == "":
            print("化疗记录内容为空，跳过")
            continue

        if "CRT_TM" in record and record["CRT_TM"]:
            record_time = self.converter.format_date(record["CRT_TM"])
            print(f"化疗记录使用CRT_TM作为创建时间: {record_time}")
        elif "RCD_DT" in record and record["RCD_DT"]:
            record_time = self.converter.format_date(record["RCD_DT"])
            print(f"化疗记录使用RCD_DT作为创建时间: {record_time}")
        else:
            record_time = "xxx"

        if len(dcmt_content) < 100:
            results.append(
                {
                    "时间": record_time,
                    "化疗药品名称": dcmt_content[:50] + "..." if len(dcmt_content) > 50 else dcmt_content,
                    "药品剂量": "文本中未提及该内容",
                    "化疗方案": "文本中未提及该内容",
                    "化疗周期": "文本中未提及该内容",
                    "化疗日期": "文本中未提及该内容",
                    "化疗反应": "文本中未提及该内容",
                    "化疗效果": "文本中未提及该内容",
                    "备注": "文本中未提及该内容",
                }
            )
            continue
        print(f"处理化疗记录，内容长度: {len(dcmt_content)}")

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

你必须严格按照以下格式返回JSON，不要添加任何其他说明，提取的信息必须严格遵循原文，严禁擅自改写或添加任何额外的内容：
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

        print("调用大模型提取化疗记录信息...")
        response = multi_model_api.chat_method_for_module("化疗记录", prompt)
        print(f"大模型响应长度: {len(response)}")

        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1

            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                print(f"提取的JSON字符串: {json_str[:200]}...")

                try:
                    extracted_data = json.loads(json_str)
                    print("成功解析化疗记录JSON")

                    doc_time = extracted_data.get("文档记录时间", "文本中未提及该内容")
                    if doc_time == "文本中未提及该内容" or doc_time == "xxx":
                        doc_time = record_time

                    results.append(
                        {
                            "时间": doc_time,
                            "化疗药品名称": extracted_data.get("化疗药品名称", "文本中未提及该内容"),
                            "药品剂量": extracted_data.get("药品剂量", "文本中未提及该内容"),
                            "化疗方案": extracted_data.get("化疗方案", "文本中未提及该内容"),
                            "化疗周期": extracted_data.get("化疗周期", "文本中未提及该内容"),
                            "化疗日期": extracted_data.get("化疗日期", "文本中未提及该内容"),
                            "化疗反应": extracted_data.get("化疗反应", "文本中未提及该内容"),
                            "化疗效果": extracted_data.get("化疗效果", "文本中未提及该内容"),
                            "备注": extracted_data.get("备注", "文本中未提及该内容"),
                        }
                    )
                except json.JSONDecodeError as e:
                    pass

                    try:
                        json_str = json_str.replace("'", '"')
                        json_str = re.sub(r"(\w+):", r'"\1":', json_str)

                        extracted_data = json.loads(json_str)
                        print("修复后成功解析化疗记录JSON")

                        doc_time = extracted_data.get("文档记录时间", "文本中未提及该内容")
                        if doc_time == "文本中未提及该内容" or doc_time == "xxx":
                            doc_time = record_time

                        results.append(
                            {
                                "时间": doc_time,
                                "化疗药品名称": extracted_data.get("化疗药品名称", "文本中未提及该内容"),
                                "药品剂量": extracted_data.get("药品剂量", "文本中未提及该内容"),
                                "化疗方案": extracted_data.get("化疗方案", "文本中未提及该内容"),
                                "化疗周期": extracted_data.get("化疗周期", "文本中未提及该内容"),
                                "化疗日期": extracted_data.get("化疗日期", "文本中未提及该内容"),
                                "化疗反应": extracted_data.get("化疗反应", "文本中未提及该内容"),
                                "化疗效果": extracted_data.get("化疗效果", "文本中未提及该内容"),
                                "备注": extracted_data.get("备注", "文本中未提及该内容"),
                            }
                        )
                    except Exception as e2:
                        pass
                        results.append(
                            {
                                "时间": record_time,
                                "化疗药品名称": dcmt_content[:100] + "..." if len(dcmt_content) > 100 else dcmt_content,
                                "药品剂量": "文本中未提及该内容",
                                "化疗方案": "文本中未提及该内容",
                                "化疗周期": "文本中未提及该内容",
                                "化疗日期": "文本中未提及该内容",
                                "化疗反应": "文本中未提及该内容",
                                "化疗效果": "文本中未提及该内容",
                                "备注": "文本中未提及该内容",
                            }
                        )
            else:
                print("未在化疗记录响应中找到JSON结构")
                results.append(
                    {
                        "时间": record_time,
                        "化疗药品名称": dcmt_content[:100] + "..." if len(dcmt_content) > 100 else dcmt_content,
                        "药品剂量": "文本中未提及该内容",
                        "化疗方案": "文本中未提及该内容",
                        "化疗周期": "文本中未提及该内容",
                        "化疗日期": "文本中未提及该内容",
                        "化疗反应": "文本中未提及该内容",
                        "化疗效果": "文本中未提及该内容",
                        "备注": "文本中未提及该内容",
                    }
                )
        except Exception as e:
            print(f"处理化疗记录大模型响应时出错: {e}")
            results.append(
                {
                    "时间": record_time,
                    "化疗药品名称": dcmt_content[:100] + "..." if len(dcmt_content) > 100 else dcmt_content,
                    "药品剂量": "文本中未提及该内容",
                    "化疗方案": "文本中未提及该内容",
                    "化疗周期": "文本中未提及该内容",
                    "化疗日期": "文本中未提及该内容",
                    "化疗反应": "文本中未提及该内容",
                    "化疗效果": "文本中未提及该内容",
                    "备注": "文本中未提及该内容",
                }
            )

    def parse_date_safe(date_str):
        if not date_str or date_str == "xxx" or date_str == "文本中未提及该内容":
            return datetime.min
        try:
            formats = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日"]
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            return datetime.max
        except Exception:
            return datetime.max

    results.sort(key=lambda x: parse_date_safe(x["时间"]))

    return results
