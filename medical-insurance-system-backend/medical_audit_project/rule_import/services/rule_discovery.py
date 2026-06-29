"""规则抽取层：结构化表格 -> 医保审核规则

迁移自 rule-import/convert-v2.py（连字符文件名不可 import，改名 rule_discovery）。
改动点：
  - 移除硬编码 OpenAI key/base_url，统一用 llm_client（配置驱动）
  - print 改 logging；tqdm 进度条改为日志（服务端无终端）
  - 支持 progress_cb 回调，便于 Celery 任务回写进度
  - 移除 __main__ 与本机绝对路径
抽取 prompt 与核心逻辑保持不变。
"""

import json
import logging
import re

from .llm_client import call_llm, get_extract_model

logger = logging.getLogger(__name__)


# 规则类型枚举（与算法 README 对齐）
RULE_TYPES = [
    "DRUG_RESTRICTION",
    "FREQUENCY_LIMIT",
    "DUPLICATE_CHARGE",
    "PRICE_LIMIT",
    "CONSUMABLE_RESTRICTION",
    "OVER_EXAMINATION",
    "OTHER",
]


def extract_json_from_llm(text):
    if not text:
        return []
    text = text.strip()
    text = re.sub(r"```json", "", text)
    text = re.sub(r"```", "", text)
    if '</think>' in text:
        text=text.split('</think>')[-1].strip()
    logger.info(text)
    match = re.search(r"\[\s*.*\s*\]", text, re.S)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception as e:  # noqa: BLE001
            logger.warning("LLM 返回 JSON 解析失败: %s", e)
    return []


def should_keep_row(row):
    priority_fields = ["备注", "说明", "项目内涵", "计价单位"]
    for field in priority_fields:
        value = str(row.get(field, "")).strip()
        if value and value.lower() != "nan":
            return True
    total = len(row)
    if total == 0:
        return False
    empty_count = 0
    for v in row.values():
        if v is None or str(v).strip() == "" or str(v).lower() == "nan":
            empty_count += 1
    return (empty_count / total) < 0.5


def filter_tables(tables):
    filtered_tables = []
    for table in tables:
        rows = table.get("rows", [])
        new_rows = [row for row in rows if should_keep_row(row)]
        table["rows"] = new_rows
        if new_rows:
            filtered_tables.append(table)
    return filtered_tables


def build_prompt(headers, rows):
    return f"""
   你是一个医保规则抽取与结构化系统。

    任务：
    从医保目录、药品目录、耗材目录、收费项目目录等表格数据中发现并提取医保审核规则。
    
    规则可能来源于：
    - 项目内涵
    - 备注
    - 说明
    - 限制条件
    - 支付条件
    - 价格说明
    - 计价单位
    - 除外内容
    
    可能包含隐含知识
   - 项目计价单位:XX → 项目的计价单位只能为xx
   - 项目A的项目内涵包含项目B” → 项目A和项目B不能同时收取

    禁止使用医学常识补充规则。
    禁止推测表格中不存在的信息。
    只能依据输入数据中的明确内容进行抽取。
    ========================
    【医保规则体系】
    ========================

    医保审核规则可分为两大类：

    1. 单对象约束规则
    针对单个药品、耗材、诊疗项目或收费项目本身设置限制条件。

    2. 多对象关联规则
    通过多个医疗对象之间的关系进行约束。

    典型对象关系：

    - 医嘱 ↔ 检查检验
    - 医嘱 ↔ 收费项目
    - 收费项目 ↔ 收费项目

    违规表现：

    - 逻辑不一致
    - 适应症不匹配
    - 缺乏支撑依据
    - 重复收费

    ========================
    【规则类型】
    ========================

    1. DRUG_RESTRICTION（药品超限定）

    规则特征：
    - 限XX疾病
    - 限XX适应症
    - 限二线治疗
    - 限特定年龄
    - 限特定科室

    违规表现：
    患者条件不满足仍收费。


    2. FREQUENCY_LIMIT（超频次收费）

    规则特征：
    - 单日上限X次
    - 每日不超过X次
    - 在设定的周期内超出限定支付数量,周期为7天，限制次数为1
    - 计价单位为日，每日不超过1次

    违规表现：
    收费次数超过规定次数。


    3. DUPLICATE_CHARGE（重复收费）

    规则特征：
    - 项目A包含项目B
    - 已收取A不得再收取B
    - 不得同时收费
    - 不得重复收费

    违规表现：
    同类项目重复收费。


    4. PRICE_LIMIT（超标准收费）

    规则特征：
    - 收费单位说明
    - 加收减收说明

    违规表现：
    收费金额超过标准。

    具体规则示例：
    胃肠减压原价15元插胃管加收10元。

    5. Overtreatment(过度医疗)

    规则特征：
    - 治疗措施超过患者实际病情需要
    - 患者短期内重复进行相同或类似的大型检查

    违规表现：
    不必要治疗/不合理住院/不必要手术


    6. OTHER

    无法归入以上类别但能够形成可执行审核逻辑的规则。

    ----------------------------------

    如果不存在规则：

    返回

    []

    ----------------------------------

    如果存在规则：

    返回格式：

    [
    {{
        "rule_type":"",
        "constrained_object":"",
        "constraint_value":"",
        "evidence":{{}}
    }}
    ]
    
    要求：

    1.rule_type必须从枚举中选择,或者文本中有明确的规则类型
        -如果判断不属于以上6类并且文本中有明确的规则类型,则可以采取文本中的规则类型作为规则类型

    2.constrained_object为规则约束对象。
        可填写：
        - 药品名称
        - 诊疗项目名称
        - 耗材名称
        - 收费项目名称
        如果规则针对的是患者行为、住院过程、病历管理等，
        不存在明确约束对象，则置空：
        "constrained_object":""

    3.constraint_value为具体限制，即具体的违规限制

    4.evidence直接返回触发规则的原始JSON行

    5.不要解释

    6.如果是显式规则不要改写，如果是隐式规则则可以根据相关知识改写，明确有违规检出逻辑的，将其作为constraint_value

    ----------------------------------

    ----------------------------------
    表头:
    {headers}

    数据:
    {json.dumps(rows, ensure_ascii=False, indent=2)}
    """


def extract_rules_from_table(table, max_rows_per_table=40, chunk_size=20):
    rows = table.get("rows", [])[:max_rows_per_table]
    all_rules = []
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start:start + chunk_size]
        prompt = build_prompt(table["headers"], chunk)
        result = call_llm(prompt, model=get_extract_model())
        rules = extract_json_from_llm(result)
        if isinstance(rules, list):
            all_rules.extend(rules)
    return all_rules


def extract_rules(tables, max_rows_per_table=40, chunk_size=20, progress_cb=None):
    """从全部表格抽取规则。

    progress_cb(done_tables, total_tables, rules_found) 可选回调，
    供 Celery 任务回写进度。
    """
    all_rules = []
    rule_id = 1
    total_tables = len(tables)
    logger.info("开始处理 %s 个表格...", total_tables)

    for idx, table in enumerate(tables):
        logger.info("处理表 %s/%s (行数=%s)", idx + 1, total_tables,
                    len(table.get("rows", [])))
        rules = extract_rules_from_table(
            table, max_rows_per_table=max_rows_per_table, chunk_size=chunk_size,
        )
        for rule in rules:
            rule["rule_id"] = rule_id
            rule["source"] = table.get("source", {})
            all_rules.append(rule)
            rule_id += 1
        if progress_cb:
            try:
                progress_cb(idx + 1, total_tables, len(all_rules))
            except Exception as e:  # noqa: BLE001 - 回调异常不应中断抽取
                logger.warning("进度回调异常(忽略): %s", e)

    logger.info("规则抽取完成，共 %s 条", len(all_rules))
    return all_rules


def discover_rules(tables, max_tables=None, max_rows_per_table=80,
                   chunk_size=20, save_json=False, output_file=None,
                   progress_cb=None):
    tables = filter_tables(tables)
    if max_tables:
        tables = tables[:max_tables]

    rules = extract_rules(
        tables, max_rows_per_table=max_rows_per_table,
        chunk_size=chunk_size, progress_cb=progress_cb,
    )

    if save_json and output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)

    return rules
