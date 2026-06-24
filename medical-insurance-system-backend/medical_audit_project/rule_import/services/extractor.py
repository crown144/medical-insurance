"""文件解析层：PDF / Excel -> 结构化表格 JSON

迁移自 rule-import/extractor.py，改动点：
  - 移除硬编码的 OpenAI key / base_url，改用 llm_client（配置驱动）
  - print 改为 logging
  - pdfplumber / pandas 惰性导入（无依赖时模块仍可加载，便于单测）
  - 移除 __main__ 与本机绝对路径
核心解析逻辑保持不变。
"""

import logging
import os
import re

from .llm_client import call_llm, get_header_model

logger = logging.getLogger(__name__)


# =========================
# 表头清洗
# =========================
def clean_header(headers):
    cleaned = []
    for h in headers:
        if h:
            h = str(h).strip()
            h = h.replace("\n", "")
            h = h.replace("（", "(").replace("）", ")")
            cleaned.append(h)
        else:
            cleaned.append("")
    return cleaned


# =========================
# 填充合并单元格
# =========================
def fill_down_rows(rows, headers):
    last_values = {h: "" for h in headers}
    new_rows = []
    for row in rows:
        new_row = {}
        for h in headers:
            val = row.get(h, "").strip()
            if val == "":
                val = last_values[h]
            else:
                last_values[h] = val
            new_row[h] = val
        new_rows.append(new_row)
    return new_rows


# =========================
# 修复缺失表头
# =========================
def fix_missing_headers(tables):
    prev_headers = None
    for t in tables:
        headers = t["headers"]
        if not headers or all(h is None or str(h).strip() == "" for h in headers):
            if prev_headers:
                t["headers"] = prev_headers
        else:
            prev_headers = headers
    return tables


def rule_is_header(headers):
    empty_count = sum(1 for h in headers if not h or str(h).strip() == "")
    if empty_count > len(headers) * 0.5:
        return False
    bad_keywords = ["★", "(", ")", "注射剂", "口服"]
    if any(any(k in str(h) for k in bad_keywords) for h in headers):
        return False
    return True


def llm_is_header(headers, first_rows):
    prompt = f"""
你是医保政策表格解析专家。

当前PDF页面提取的第一行如下：
{headers}


下面是该表格的前2行数据：
{first_rows[:2]}

任务：
判断这一页的第一行是否是表头，还是上一页pdf的续表，如果是续表输出false，如果这一页的第一行是表头则输出true。

判断标准：
1. 表头应该是字段名称（如：药品名称、编号、剂型等）
2. 不应该是具体数据（如：乙、★(15)、18、兰索拉唑等）
3. 表头通常具有概括性，而不是具体值
输出：
只返回 true 或 false
"""
    result = call_llm(prompt, model=get_header_model())
    if any(k in result for k in ["true", "yes", "是"]):
        return True
    if any(k in result for k in ["false", "no", "否"]):
        return False
    return False


# =========================
# 合并跨页表格（PDF专用）
# =========================
def merge_cross_page_tables(tables):
    if not tables:
        return []
    merged = []
    prev = tables[0]
    for curr in tables[1:]:
        prev_headers = clean_header(prev["headers"])
        curr_headers = clean_header(curr["headers"])
        prev_page = prev["source"].get("page")
        curr_page = curr["source"].get("page")
        if (
            prev_headers == curr_headers and
            prev_page is not None and
            curr_page == prev_page + 1
        ):
            prev["rows"].extend(curr["rows"])
            prev["source"]["page_end"] = curr_page
        else:
            merged.append(prev)
            prev = curr
    merged.append(prev)
    return merged


def find_real_header_row(table):
    """找到真正的表头行（不是空行或标题行）"""
    header_keywords = ['序号', '项目名称', '医疗服务项目名称', '检出逻辑',
                       '逻辑依据', '项目代码', '药品名称', '药品代码']
    for i, row in enumerate(table[:6]):
        if not row:
            continue
        row_str = ' '.join([str(cell) for cell in row if cell])
        for keyword in header_keywords:
            if keyword in row_str:
                return i
    for i, row in enumerate(table[:6]):
        if row and any(cell and str(cell).strip() for cell in row):
            row_str = ' '.join([str(cell) for cell in row if cell])
            if not any(kw in row_str for kw in ['规则对应知识点']):
                return i
    return 0


def extract_pdf_tables(file_path, max_pages=None):
    import pdfplumber

    results = []
    with pdfplumber.open(file_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            if max_pages is not None and page_idx >= max_pages:
                break
            tables = page.extract_tables()
            for t_idx, table in enumerate(tables):
                if not table or len(table) < 2:
                    continue

                header_row_idx = find_real_header_row(table)
                candidate_headers = clean_header(table[header_row_idx])
                candidate_rows = table[header_row_idx + 1:]

                is_header = True
                if results:
                    try:
                        if rule_is_header(candidate_headers):
                            is_header = llm_is_header(candidate_headers,
                                                      candidate_rows[:2])
                        else:
                            is_header = False
                    except Exception as e:  # noqa: BLE001
                        logger.warning("LLM 判断表头失败，按非表头处理: %s", e)
                        is_header = False

                if not is_header and results:
                    headers = results[-1]["headers"]
                    rows = candidate_rows
                else:
                    headers = candidate_headers
                    rows = candidate_rows

                structured_rows = []
                for row in rows:
                    if not row or all(cell is None or str(cell).strip() == ''
                                      for cell in row):
                        continue
                    row_dict = {}
                    for h, v in zip(headers, row):
                        if h:
                            value = str(v).strip() if v else ""
                            if value and value.lower() != 'none':
                                row_dict[h] = value
                    if row_dict:
                        structured_rows.append(row_dict)

                if structured_rows:
                    results.append({
                        "source": {
                            "file_name": os.path.basename(file_path),
                            "type": "pdf",
                            "page": page_idx + 1,
                            "table_index": t_idx,
                        },
                        "headers": headers,
                        "rows": structured_rows,
                    })

    results = fix_missing_headers(results)
    results = merge_cross_page_tables(results)
    return results


# =========================
# 判断是否多级表头
# =========================
def is_multi_header(df):
    import pandas as pd

    if len(df) < 2:
        return False
    first_row = df.iloc[0].fillna("")
    second_row = df.iloc[1]
    non_empty_count = sum(
        1 for x in second_row if pd.notna(x) and str(x).strip()
    )
    return non_empty_count <= len(first_row) * 0.5


def build_multi_headers(df):
    row1 = df.iloc[0].fillna("")
    row2 = df.iloc[1].fillna("")
    headers = []
    parent = ""
    for i in range(len(row1)):
        v1 = str(row1.iloc[i]).strip()
        v2 = str(row2.iloc[i]).strip()
        if v1:
            parent = v1
        if v2:
            headers.append(f"{parent}_{v2}")
        else:
            headers.append(parent)
    return clean_header(headers)


def is_category_row(row_values):
    import pandas as pd

    non_empty = [
        str(x).strip() for x in row_values if pd.notna(x) and str(x).strip()
    ]
    if len(non_empty) > 3:
        return False
    text = " ".join(non_empty)
    patterns = [
        r"^（[一二三四五六七八九十]+）",
        r"^\([一二三四五六七八九十]+\)",
        r"^\d+\.",
        r"^[一二三四五六七八九十]+、",
    ]
    for p in patterns:
        if re.search(p, text):
            return True
    if len(non_empty) == 2:
        code = non_empty[0]
        if code.isdigit() and len(code) <= 8:
            return True
    return False


def extract_excel_tables(file_path):
    import pandas as pd

    results = []
    logger.info("开始解析 Excel: %s", file_path)
    xls = pd.ExcelFile(file_path)

    for sheet_name in xls.sheet_names:
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name,
                               header=None, dtype=str)
        except Exception as e:  # noqa: BLE001
            logger.warning("读取 sheet 失败: %s (%s)", sheet_name, e)
            continue

        df = df.dropna(how="all")
        df = df.dropna(axis=1, how="all")
        if df.empty:
            continue

        if is_multi_header(df):
            headers = build_multi_headers(df)
            data_df = df.iloc[2:].reset_index(drop=True)
        else:
            headers = clean_header([str(x).strip() for x in df.iloc[0]])
            data_df = df.iloc[1:].reset_index(drop=True)

        headers = headers[:len(data_df.columns)]
        rows = []
        current_category = ""

        for _, row in data_df.iterrows():
            row_values = row.tolist()
            if is_category_row(row_values):
                current_category = " > ".join(
                    [str(x).strip() for x in row_values
                     if pd.notna(x) and str(x).strip()]
                )
                continue

            row_dict = {}
            for col_idx, col_name in enumerate(headers):
                if not col_name:
                    continue
                try:
                    value = row.iloc[col_idx]
                except Exception:  # noqa: BLE001
                    value = ""
                row_dict[col_name] = (
                    str(value).strip() if pd.notna(value) else ""
                )

            if not any(str(v).strip() for v in row_dict.values()):
                continue
            if current_category:
                row_dict["所属目录"] = current_category
            rows.append(row_dict)

        if rows:
            results.append({
                "source": {
                    "file_name": os.path.basename(file_path),
                    "type": "excel",
                    "sheet_name": sheet_name,
                },
                "headers": headers,
                "rows": rows,
            })

    return results


def extract_tables(file_path, max_pdf_pages=None):
    logger.info("解析文件: %s", file_path)
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return extract_pdf_tables(file_path, max_pdf_pages)
    elif ext in [".xlsx", ".xls"]:
        return extract_excel_tables(file_path)
    else:
        raise ValueError("支持 PDF / Excel 文件")


def file_to_json(file_path, max_pdf_pages=None, save_json=False, output_file=None):
    """文件转结构化表格 JSON。"""
    tables = extract_tables(file_path=file_path, max_pdf_pages=max_pdf_pages)

    if save_json and output_file:
        import json
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(tables, f, ensure_ascii=False, indent=2)

    return tables
