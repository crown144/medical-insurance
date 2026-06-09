"""
Excel 列自动识别服务
多策略识别：正则匹配 → 数据模式验证 → LLM 辅助分析
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


# ==================== 目标字段定义 ====================

@dataclass
class TargetField:
    """目标字段定义"""
    key: str                              # 字段key
    label: str                            # 中文标签
    patterns: List[str]                   # 列名匹配正则
    data_validator: Optional[str] = None  # 数据类型验证器名


# 需要识别的目标字段
TARGET_FIELDS: List[TargetField] = [
    TargetField(
        key='hospitalization_no',
        label='住院号',
        patterns=[
            r'住院号', r'住院编号', r'病历号', r'病案号', r'住院号$',
            r'hospitalization', r'inpatient.?no', r'admission.?no',
            r'patient.?id$', r'病历号$', r'流水号',
        ],
        data_validator='hospitalization_no',
    ),
    TargetField(
        key='patient_name',
        label='患者姓名',
        patterns=[
            r'患者姓名', r'病人姓名', r'姓名$', r'患者$',
            r'patient.?name', r'name$',
        ],
    ),
    TargetField(
        key='hospital_name',
        label='医疗机构',
        patterns=[
            r'医疗机构', r'医院名称', r'医院$', r'机构名称',
            r'hospital', r'institution', r'org.?name',
            r'定点机构', r'医药机构',
        ],
    ),
    TargetField(
        key='issue_category',
        label='问题类别',
        patterns=[
            r'问题类型', r'违规类型', r'问题类别', r'违规类别',
            r'问题性质', r'违规项目', r'检查类型',
            r'issue.?type', r'violation.?type', r'category',
            r'问题大类', r'违规大类',
        ],
    ),
    TargetField(
        key='issue_description',
        label='问题描述',
        patterns=[
            r'问题描述', r'违规描述', r'描述$', r'具体情况',
            r'description', r'detail', r'finding',
            r'违规内容', r'检查发现', r'问题详情',
        ],
    ),
    TargetField(
        key='involved_amount',
        label='涉及金额',
        patterns=[
            r'涉及金额', r'违规金额', r'金额$', r'费用$',
            r'amount', r'fee', r'cost', r'money',
            r'金额.*元', r'违规费用', r'涉案金额',
            r'核定金额', r'追回金额',
        ],
        data_validator='amount',
    ),
    TargetField(
        key='admission_date',
        label='入院日期',
        patterns=[
            r'入院日期', r'入院时间', r'住院日期',
            r'admission.?date', r'in.?date', r'start.?date',
            r'住院开始', r'开始日期',
        ],
        data_validator='date',
    ),
    TargetField(
        key='discharge_date',
        label='出院日期',
        patterns=[
            r'出院日期', r'出院时间', r'结算日期',
            r'discharge.?date', r'out.?date', r'end.?date',
            r'住院结束', r'结束日期',
        ],
        data_validator='date',
    ),
    TargetField(
        key='audit_org',
        label='飞检机构',
        patterns=[
            r'飞检机构', r'检查机构', r'审计机构', r'检查组',
            r'audit.?org', r'inspection.?org',
            r'检查单位', r'审计单位',
        ],
    ),
    TargetField(
        key='audit_date',
        label='飞检日期',
        patterns=[
            r'飞检日期', r'检查日期', r'审计日期',
            r'audit.?date', r'inspection.?date',
            r'检查时间',
        ],
        data_validator='date',
    ),
]


# ==================== 数据验证器 ====================

def validate_hospitalization_no(values: pd.Series) -> float:
    """验证住院号模式：应为非空、合理长度的字符串"""
    non_null = values.dropna().astype(str)
    if len(non_null) == 0:
        return 0.0
    # 检查：大部分值长度在6-30之间，不含中文字符过多
    valid = non_null.apply(
        lambda x: 6 <= len(str(x).strip()) <= 30
        and not bool(re.search(r'[一-鿿]{5,}', str(x)))
    )
    return valid.mean()  # 返回有效比例


def validate_amount(values: pd.Series) -> float:
    """验证金额模式：应为正数"""
    non_null = values.dropna()
    if len(non_null) == 0:
        return 0.0
    try:
        numeric = pd.to_numeric(non_null, errors='coerce').dropna()
        if len(numeric) == 0:
            return 0.0
        # 大部分值应为正数
        positive_ratio = (numeric >= 0).mean()
        return positive_ratio * (len(numeric) / len(non_null))
    except Exception:
        return 0.0


def validate_date(values: pd.Series) -> float:
    """验证日期模式"""
    non_null = values.dropna().astype(str)
    if len(non_null) == 0:
        return 0.0
    date_patterns = [
        r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',        # 2024-01-15
        r'\d{4}年\d{1,2}月\d{1,2}日',           # 2024年1月15日
        r'\d{1,2}[-/]\d{1,2}[-/]\d{4}',          # 01/15/2024
    ]
    valid_count = 0
    for val in non_null:
        val_str = str(val).strip()
        if any(re.search(p, val_str) for p in date_patterns):
            valid_count += 1
        else:
            # 也可能直接是日期类型
            try:
                pd.Timestamp(val_str)
                valid_count += 1
            except Exception:
                pass
    return valid_count / len(non_null)


VALIDATORS = {
    'hospitalization_no': validate_hospitalization_no,
    'amount': validate_amount,
    'date': validate_date,
}


# ==================== 列分析结果 ====================

@dataclass
class ColumnMatch:
    """列匹配结果"""
    field_key: str
    field_label: str
    column_name: str          # 原始列名
    column_index: int         # 列索引(0-based)
    confidence: float         # 匹配置信度 0-1
    method: str               # 匹配方法: regex / regex+data / llm


@dataclass
class AnalysisResult:
    """分析结果"""
    columns: List[str]                           # 所有列名
    sample_rows: List[Dict[str, Any]]            # 样本数据(前5行)
    mappings: List[ColumnMatch]                  # 列映射结果
    unmapped_fields: List[str]                   # 未匹配到的字段
    unmapped_columns: List[str]                  # 未识别的列
    llm_analysis: Optional[str] = None           # LLM 分析结果


# ==================== 核心分析器 ====================

class ExcelColumnAnalyzer:
    """
    Excel 列自动识别器

    三阶段策略：
    1. 正则匹配列名 → 得到候选映射
    2. 数据模式验证 → 提升/降低置信度
    3. LLM 辅助分析 → 处理无法识别的列（可选）
    """

    def __init__(self, enable_llm: bool = True):
        self.enable_llm = enable_llm

    def analyze(
        self,
        file_path: str,
        sheet_name: Optional[str] = None,
    ) -> AnalysisResult:
        """
        分析 Excel 文件，自动识别列映射

        Args:
            file_path: Excel 文件路径
            sheet_name: 工作表名（None 则取第一个）

        Returns:
            AnalysisResult 包含列映射建议
        """
        # 读取 Excel
        df = self._read_dataframe(file_path, sheet_name=sheet_name, nrows=100)

        # 清理列名
        df.columns = [str(c).strip() for c in df.columns]
        columns = list(df.columns)

        # 阶段1: 正则匹配
        mappings = self._regex_match(columns, df)

        # 阶段2: 数据模式验证
        mappings = self._validate_with_data(mappings, df)

        # 阶段3: LLM 辅助分析
        llm_result = None
        if self.enable_llm:
            unmapped = [f.key for f in TARGET_FIELDS
                        if not any(m.field_key == f.key for m in mappings)]
            unknown_cols = [c for c in columns
                            if not any(m.column_name == c for m in mappings)]
            if unmapped or unknown_cols:
                llm_result = self._llm_analyze(columns, df, unmapped, unknown_cols)
                if llm_result:
                    llm_mappings = self._parse_llm_result(llm_result, columns)
                    mappings.extend(llm_mappings)

        # 构建结果
        unmapped_fields = [f.key for f in TARGET_FIELDS
                           if not any(m.field_key == f.key for m in mappings)]
        unmapped_columns = [c for c in columns
                            if not any(m.column_name == c for m in mappings)]

        # 样本数据
        sample_df = df.head(5)
        sample_rows = []
        for _, row in sample_df.iterrows():
            sample_rows.append({
                str(k): _safe_convert(row[k])
                for k in df.columns
            })

        return AnalysisResult(
            columns=columns,
            sample_rows=sample_rows,
            mappings=mappings,
            unmapped_fields=unmapped_fields,
            unmapped_columns=unmapped_columns,
            llm_analysis=llm_result,
        )

    def _read_dataframe(
        self,
        file_path: str,
        sheet_name: Optional[str] = None,
        nrows: Optional[int] = None,
    ) -> pd.DataFrame:
        suffix = Path(file_path).suffix.lower()
        if suffix == '.csv':
            return pd.read_csv(file_path, nrows=nrows)
        if sheet_name:
            return pd.read_excel(file_path, sheet_name=sheet_name, nrows=nrows)
        return pd.read_excel(file_path, nrows=nrows)

    def _regex_match(
        self, columns: List[str], df: pd.DataFrame,
    ) -> List[ColumnMatch]:
        """阶段1: 正则匹配列名"""
        matches = []

        for idx, col_name in enumerate(columns):
            col_lower = col_name.lower().strip()

            for field in TARGET_FIELDS:
                best_score = 0.0
                best_pattern = ''

                for pattern in field.patterns:
                    if re.search(pattern, col_lower, re.IGNORECASE):
                        # 精确匹配分数更高
                        if re.fullmatch(pattern, col_lower, re.IGNORECASE):
                            score = 0.9
                        elif col_lower.startswith(pattern.replace('$', '')):
                            score = 0.85
                        else:
                            score = 0.7
                        if score > best_score:
                            best_score = score
                            best_pattern = pattern

                if best_score > 0:
                    matches.append(ColumnMatch(
                        field_key=field.key,
                        field_label=field.label,
                        column_name=col_name,
                        column_index=idx,
                        confidence=best_score,
                        method='regex',
                    ))

        # 去重：同一列取最高分，同一字段取最高分
        return self._deduplicate_matches(matches)

    def _validate_with_data(
        self, mappings: List[ColumnMatch], df: pd.DataFrame,
    ) -> List[ColumnMatch]:
        """阶段2: 数据模式验证"""
        for match in mappings:
            field = next((f for f in TARGET_FIELDS
                          if f.key == match.field_key), None)
            if not field or not field.data_validator:
                continue

            validator = VALIDATORS.get(field.data_validator)
            if not validator:
                continue

            col_name = match.column_name
            if col_name not in df.columns:
                continue

            data_score = validator(df[col_name])

            # 数据验证调整置信度
            if data_score >= 0.8:
                match.confidence = min(1.0, match.confidence * 1.2)
                match.method = 'regex+data'
            elif data_score < 0.3:
                match.confidence *= 0.5
            else:
                match.confidence = match.confidence * (0.7 + 0.3 * data_score)
                match.method = 'regex+data'

        return mappings

    def _llm_analyze(
        self,
        columns: List[str],
        df: pd.DataFrame,
        unmapped_fields: List[str],
        unknown_columns: List[str],
    ) -> Optional[str]:
        """阶段3: LLM 辅助分析"""
        try:
            from engine.llm_api import chat_completion
        except ImportError:
            return None

        # 准备列信息和样本数据
        sample_data = []
        for i in range(min(5, len(df))):
            row = {str(k): str(df.iloc[i][k]) for k in df.columns[:20]}
            sample_data.append(row)

        field_labels = {
            f.key: f.label
            for f in TARGET_FIELDS
            if f.key in unmapped_fields
        }

        prompt = f"""你是一个医疗数据分析专家。请分析以下飞检Excel文件的列结构，帮我在未知列中识别目标字段。

所有列名: {columns}

还未匹配的目标字段: {field_labels}

还未识别的列: {unknown_columns}

前5行样本数据:
{_format_sample(sample_data)}

请以JSON格式返回你的分析结果，格式如下:
{{
    "mappings": [
        {{"column": "原始列名", "field_key": "目标字段key", "reason": "判断依据"}}
    ]
}}

注意:
- 目标字段key从 {list(field_labels.keys())} 中选择
- 住院号通常是字母数字组合，长度6-20位
- 金额是正数，可能带"元"后缀
- 日期格式可能是 2024-01-15 或 2024年1月15日
- 问题类别/描述通常是较长的文本
- 医疗机构名称通常包含"医院"、"中心"等词

如果某列无法对应任何目标字段，请不要包含在mappings中。"""

        try:
            response = chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            return response
        except Exception as e:
            return f"LLM分析失败: {str(e)}"

    def _parse_llm_result(
        self, llm_response: str, columns: List[str],
    ) -> List[ColumnMatch]:
        """解析 LLM 返回的 JSON 结果"""
        import json

        # 尝试从响应中提取 JSON
        json_match = re.search(r'\{[\s\S]*\}', llm_response)
        if not json_match:
            return []

        try:
            data = json.loads(json_match.group())
            mappings_data = data.get('mappings', [])
        except json.JSONDecodeError:
            return []

        results = []
        for item in mappings_data:
            col_name = item.get('column', '')
            field_key = item.get('field_key', '')

            # 验证列名存在
            if col_name not in columns:
                # 尝试模糊匹配
                for c in columns:
                    if col_name.lower() in c.lower() or c.lower() in col_name.lower():
                        col_name = c
                        break
                else:
                    continue

            # 验证 field_key 合法
            valid_keys = {f.key for f in TARGET_FIELDS}
            if field_key not in valid_keys:
                continue

            field = next(f for f in TARGET_FIELDS if f.key == field_key)
            results.append(ColumnMatch(
                field_key=field_key,
                field_label=field.label,
                column_name=col_name,
                column_index=columns.index(col_name),
                confidence=0.75,  # LLM结果默认0.75置信度
                method='llm',
            ))

        return results

    def _deduplicate_matches(
        self, matches: List[ColumnMatch],
    ) -> List[ColumnMatch]:
        """去重：每个字段保留置信度最高的匹配"""
        best_per_field: Dict[str, ColumnMatch] = {}
        for m in matches:
            if (m.field_key not in best_per_field
                    or m.confidence > best_per_field[m.field_key].confidence):
                best_per_field[m.field_key] = m

        # 同时检查同一列被多个字段匹配
        used_columns = set()
        result = []
        for m in sorted(best_per_field.values(),
                        key=lambda x: x.confidence, reverse=True):
            if m.column_name not in used_columns:
                result.append(m)
                used_columns.add(m.column_name)

        return result


# ==================== 辅助函数 ====================

def _safe_convert(value: Any) -> Any:
    """安全转换值为JSON可序列化格式"""
    if pd.isna(value):
        return ''
    if isinstance(value, (pd.Timestamp,)):
        return value.strftime('%Y-%m-%d')
    if isinstance(value, (Decimal,)):
        return float(value)
    if isinstance(value, (int, float, str, bool)):
        return value
    return str(value)


def _format_sample(sample_data: List[Dict]) -> str:
    """格式化样本数据为简洁字符串"""
    if not sample_data:
        return '(无数据)'

    lines = []
    for i, row in enumerate(sample_data[:3]):
        items = [f"  {k}: {v}" for k, v in list(row.items())[:10]]
        lines.append(f"第{i+1}行:\n" + '\n'.join(items))
    return '\n\n'.join(lines)
