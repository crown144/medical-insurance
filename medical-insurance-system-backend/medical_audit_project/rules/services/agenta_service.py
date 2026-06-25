from __future__ import annotations

import ast
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from django.conf import settings
from openai import OpenAI


TEMP_DISABLE_LLM_ENV = 'AGENTA_DISABLE_LLM_TEST'


@dataclass
class AgentAGenerationResult:
    rule_text: str
    system_prompt: dict[str, Any]
    tool_schema: list[str]
    generated_code: str
    validation: dict[str, Any]
    rule_snapshot: dict[str, Any]
    raw_output: str | None = None
    finish_reason: str | None = None


class AgentAService:
    """系统内自包含的规则编译服务，默认调用阿里云百炼 Qwen3.5。"""

    @classmethod
    def _llm_config(cls) -> dict[str, Any]:
        return {
            'base_url': cls._normalize_base_url(
                getattr(
                    settings,
                    'RULE_COMPILE_LLM_BASE_URL',
                    'https://dashscope.aliyuncs.com/compatible-mode/v1',
                ),
            ),
            'model': getattr(
                settings,
                'RULE_COMPILE_LLM_MODEL',
                'qwen3.5-35b-a3b',
            ),
            'api_key': getattr(settings, 'RULE_COMPILE_LLM_API_KEY', '') or '',
            'max_tokens': int(
                getattr(settings, 'RULE_COMPILE_LLM_MAX_TOKENS', 6000),
            ),
            'timeout': int(
                getattr(settings, 'RULE_COMPILE_LLM_TIMEOUT', 120),
            ),
        }

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        base_url = (base_url or '').strip().rstrip('/')
        parsed = urlparse(base_url)
        if parsed.scheme and parsed.netloc and parsed.path in {'', '/'}:
            return f'{base_url}/v1'
        return base_url

    @classmethod
    def is_temp_llm_disabled(cls) -> bool:
        return os.environ.get(TEMP_DISABLE_LLM_ENV, '').strip().lower() in {'1', 'true', 'yes', 'on'}

    @classmethod
    def _create_client(cls) -> tuple[OpenAI, str]:
        config = cls._llm_config()
        api_key = config['api_key']
        if not api_key:
            raise ValueError('未配置 RULE_COMPILE_LLM_API_KEY，请先在 settings 或环境变量中配置规则编译模型 API Key')
        client = OpenAI(
            api_key=api_key,
            base_url=config['base_url'],
            timeout=config['timeout'],
        )
        return client, config['model']

    @staticmethod
    def _infer_tools(rule_text: str) -> list[str]:
        tools = ['get_val', 'filter_list', 'list_contains', 'is_compare', 'submit_result']
        if any(k in rule_text for k in ['天', '日', '岁', '年', '剂量', '频次']):
            tools.append('calc_stats')
        if any(k in rule_text for k in ['确诊', '是否', '症状', '指征', '新发', '急性']):
            tools.append('llm_bool')
        return tools

    @staticmethod
    def _system_prompt(rule_text: str) -> dict[str, Any]:
        return {
            'style': 'agentA',
            'provider': 'aliyun_bailian_qwen',
            'rule_text': rule_text,
            'data_schema': {
                '收费报告': [
                    {
                        '住院号': 'xxx',
                        '收费项目名称': 'xxx',
                        '收费项目代码': 'xxx',
                        '收费日期': 'xxx',
                        '项目数量': 'xxx',
                        '项目单价': 'xxx',
                        '项目单位': 'xxx',
                        '项目费用': 'xxx',
                        '费用类别': 'xxx',
                        'ORDER_NO': 'xxx',
                        'ORDER_ITEM_CODE': 'xxx',
                    }
                ]
            },
        }

    @staticmethod
    def _build_prompt(rule_text: str, tools: list[str]) -> tuple[str, str]:
        tools_def = _tool_schema_text(tools)
        examples = _few_shot_examples()
        system_prompt = f"""
你是一名医保规则转换专家，负责将自然语言医保规则转换为标准的 Python 审核函数。

## 数据结构
{json_data_schema()}

## 可用工具函数
只能使用以下工具函数，不要 import 任何模块，不要调用未列出的函数：
{tools_def}

## 转换要求
1. 严格生成 `def execute_rule(ctx):`，并且最终必须 `return submit_result(...)`。
2. 只输出 Python 代码，不要输出解释、Markdown、标题、代码围栏。
3. 严格三阶段结构：
   - Phase 1: Prepare Data，只取值、过滤、分组、计算，不做最终判定。
   - Phase 2: Predicates，只做原子判断，例如是否命中目标项目、是否超标准、是否缺少基础项目。
   - Phase 3: Logic & Result，组合逻辑、生成 failure_message 和 evidence。
4. 项目级规则必须先判断适用范围：
   - `is_target` 必须基于项目名称、项目代码、药品名称、医嘱项目等标识字段。
   - `applicable = is_target`，没有使用目标项目时返回 `submit_result(is_applicable=False)` 或让 `is_applicable=False`。
5. 数值比较必须优先使用 `is_compare(value=..., operator=..., threshold=...)`，不要直接写 `>`、`>=`、`<`、`<=`。
6. 费用规则要区分基础项目、加收项目、缺少基础项目、基础项目超价、加收项目超价，错误从严重到轻微排序。
7. `llm_bool` 是昂贵语义判断，只能在硬规则无法确认时延迟调用；先做诊断编码、诊断名称、项目名称等硬逻辑匹配。
8. evidence 必须是 dict，避免塞入整份病历；只保留人工复核需要的关键变量、命中项目、错误详情。
9. evidence 内必须包含 `highlights` 字段，格式必须是列表，每一项包含：
   - `field_path`: 字段路径，优先使用 `$.收费报告[索引].字段名`、`$.诊断信息[索引].字段名`、`$.用药信息[索引].字段名` 这类 JSONPath 风格。
   - `highlighted_text`: 需要前端高亮/展示的原始值，必须转成字符串。
10. evidence 推荐结构：
   {{
       "summary": {{"关键统计": "..."}},
       "highlights": [{{"field_path": "$.收费报告[0].项目单价", "highlighted_text": "23"}}],
       "items": {{"target_items": [...], "error_details": [...]}}
   }}
11. 如果 evidence 中记录了命中项目列表，也要为每个关键命中项补充对应 highlights；如果无法确定精确索引，field_path 可以退化为 `"收费报告.收费项目名称"`，但 highlighted_text 必须是实际命中文本。
12. 变量命名要有业务含义，代码必须稳定、可执行、能通过 ast.parse。

## 示例规则转换
{examples}

现在请将用户提供的自然语言医保规则转换为符合以上所有要求的 Python 函数 execute_rule(ctx)。
""".strip()

        user_prompt = f'Rule: "{rule_text}"\nGenerate Python Code: /no_think'
        return system_prompt, user_prompt

    @classmethod
    def build(cls, rule_text: str) -> AgentAGenerationResult:
        tools = cls._infer_tools(rule_text)
        if cls.is_temp_llm_disabled():
            generated_code = cls._hardcoded_code(rule_text)
            validation = cls.validate_code(generated_code)
            snapshot = cls._rule_snapshot(rule_text, generated_code)
            snapshot['runtime_mode'] = 'hardcoded'
            snapshot['runtime_label'] = '临时关闭大模型'
            snapshot['raw_output'] = generated_code
            snapshot['llm_config'] = {
                'disabled': True,
                'provider': 'hardcoded_test',
            }
            return AgentAGenerationResult(
                rule_text=rule_text,
                system_prompt=cls._system_prompt(rule_text),
                tool_schema=['get_val', 'filter_list', 'llm_bool', 'submit_result'],
                generated_code=generated_code,
                validation=validation,
                rule_snapshot=snapshot,
                raw_output=generated_code,
                finish_reason='stop',
            )

        client, model = cls._create_client()
        system_prompt, user_prompt = cls._build_prompt(rule_text, tools)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            temperature=0.1,
            max_tokens=cls._llm_config()['max_tokens'],
        )

        choice = response.choices[0]
        raw_output = choice.message.content or ''
        generated_code = cls._clean_code(raw_output)
        validation = cls.validate_code(generated_code)
        snapshot = cls._rule_snapshot(rule_text, generated_code)
        snapshot['runtime_mode'] = 'llm'
        snapshot['runtime_label'] = '大模型生成'
        snapshot['raw_output'] = raw_output
        snapshot['finish_reason'] = choice.finish_reason
        snapshot['llm_config'] = {
            'base_url': cls._llm_config()['base_url'],
            'model': model,
            'provider': 'aliyun_bailian_qwen',
            'max_tokens': cls._llm_config()['max_tokens'],
        }
        return AgentAGenerationResult(
            rule_text=rule_text,
            system_prompt=cls._system_prompt(rule_text),
            tool_schema=tools,
            generated_code=generated_code,
            validation=validation,
            rule_snapshot=snapshot,
            raw_output=raw_output,
            finish_reason=choice.finish_reason,
        )

    @staticmethod
    def _clean_code(text: str) -> str:
        text = text.strip()
        if '```' in text:
            start = text.find('```')
            end = text.rfind('```')
            if start != -1 and end != -1 and end > start:
                block = text[start + 3 : end].strip()
                if block.startswith('python'):
                    block = block[6:].strip()
                return block.strip()
        return text

    @staticmethod
    def _hardcoded_code(rule_text: str) -> str:
        safe_rule_text = rule_text.replace('"""', '\"\"\"')
        return f'''def execute_rule(ctx):
    """临时关闭大模型时的固定输出。"""
    rule_text = """{safe_rule_text}"""
    admission = get_val(ctx, "入院记录", {{}})
    course = get_val(ctx, "首次病程记录", {{}})
    diagnosis_list = get_val(ctx, "诊断信息", [])

    text_blob = f"{{get_val(admission, '现病史', '')}} {{get_val(admission, '初步诊断', '')}} {{get_val(course, '文档内容', '')}}"
    diagnosis_names = []
    for item in diagnosis_list:
        if isinstance(item, dict):
            diagnosis_names.append(get_val(item, '诊断名称', ''))

    has_stroke = any('脑梗' in name or '脑卒中' in name for name in diagnosis_names)
    has_acute = any(keyword in text_blob for keyword in ['新发', '急性', '发病', '48小时'])
    passed = not (has_stroke and has_acute)

    return submit_result(
        is_applicable=True,
        is_compliant=passed,
        failure_message='' if passed else '发现拦截条件：诊断命中且存在新发/急性证据。',
        evidence={{
            'mode': 'hardcoded',
            'rule_text': rule_text,
            'diagnosis_names': diagnosis_names,
            'text_blob': text_blob[:500],
            'has_stroke': has_stroke,
            'has_acute': has_acute,
        }}
    )'''

    @staticmethod
    def validate_code(rule_code: str) -> dict[str, Any]:
        try:
            tree = ast.parse(rule_code)
            has_execute = any(
                isinstance(node, ast.FunctionDef) and node.name == 'execute_rule'
                for node in tree.body
            )
            return {'valid': has_execute, 'errors': [] if has_execute else ['missing execute_rule function']}
        except SyntaxError as exc:
            return {'valid': False, 'errors': [str(exc)]}

    @staticmethod
    def _rule_snapshot(rule_text: str, generated_code: str) -> dict[str, Any]:
        return {
            'matched_rule_id': None,
            'matched_description': rule_text,
            'generated_code_length': len(generated_code),
        }


def _tool_schema_text(tools: list[str]) -> str:
    schemas = {
        'get_val': '''
def get_val(source, path: str, default=None):
    """
    通用取值函数。支持字典字段、点路径和列表投影。
    示例：
    get_val(ctx, "收费报告", [])
    get_val(item, "收费项目名称", "")
    get_val([{"age": 10}, {"age": 20}], "age") -> [10, 20]
    """
'''.strip(),
        'filter_list': '''
def filter_list(data_list, field_path: str, match_value, operator: str = "=="):
    """
    从列表中过滤对象。
    operator:
      - "==": 精确匹配
      - "contains": 包含匹配；match_value 可为列表，表示任一关键词命中
      - "startswith": 前缀匹配；match_value 可为列表
      - "in": 白名单匹配
    """
'''.strip(),
        'list_contains': '''
def list_contains(target_list, keyword: str) -> bool:
    """判断列表中是否存在包含 keyword 的文本。"""
'''.strip(),
        'is_compare': '''
def is_compare(value, operator: str, threshold) -> bool:
    """
    类型安全比较。operator 只能是 ">", ">=", "<", "<=", "==", "!="。
    数值、金额、天数、年龄比较必须优先使用该函数。
    """
'''.strip(),
        'calc_stats': '''
def calc_stats(data_list, method: str):
    """
    统计列表。method 可为 "span_days", "max_gap", "count", "sum", "max", "min", "avg"。
    """
'''.strip(),
        'llm_bool': '''
def llm_bool(context_text: str, question: str) -> bool:
    """
    昂贵的语义判断，只能在硬规则证据不足时调用。
    context_text 应是病史、诊断、病程等少量关键文本拼接。
    question 必须是是/否问题。
    """
'''.strip(),
        'submit_result': '''
def submit_result(is_applicable: bool, is_compliant: bool = True, failure_message: str = "", evidence: dict = None) -> dict:
    """
    标准结果返回函数。所有规则最终必须返回该函数。
    is_applicable=False 表示未命中目标药品/收费项目，跳过检查。
    is_compliant=False 表示违规。
    evidence 只放人工复核需要的关键变量。
    evidence 必须包含 highlights 列表：
      [{"field_path": "$.收费报告[0].项目单价", "highlighted_text": "23"}]
    """
'''.strip(),
    }
    return '\n\n'.join(schemas[name] for name in tools if name in schemas)


def _few_shot_examples() -> str:
    return '''
Example Input: "使用艾普拉唑须有十二指肠溃疡、反流性食管炎诊断"
Example Output:
def execute_rule(ctx):
    med_list = get_val(ctx, "用药信息", default=[])
    target_items = filter_list(med_list, "药品通用名", "艾普拉唑", "contains")

    if len(target_items) == 0:
        return submit_result(is_applicable=False)

    diag_list = get_val(ctx, "诊断信息", default=[])
    matched_icd = filter_list(diag_list, "ICD编码", ["K26", "K21"], "startswith")
    target_keywords = ["十二指肠溃疡", "反流性食管炎", "胃食管反流"]
    matched_names = filter_list(diag_list, "诊断名称", target_keywords, "contains")

    has_hard_evidence = len(matched_icd) > 0 or len(matched_names) > 0
    has_ai_evidence = False

    if not has_hard_evidence:
        admission = get_val(ctx, "入院记录", default={})
        emr_context = "; ".join([
            f"现病史: {get_val(admission, '现病史', '')}",
            f"既往史: {get_val(admission, '既往史', '')}",
            f"初步诊断: {get_val(admission, '初步诊断', '')}",
        ])
        if len(emr_context) > 10:
            has_ai_evidence = llm_bool(
                context_text=emr_context,
                question="患者是否明确确诊为十二指肠溃疡或反流性食管炎？",
            )

    compliant = has_hard_evidence or has_ai_evidence
    fail_msg = ""
    if not compliant:
        fail_msg = "适应症不符：艾普拉唑限十二指肠溃疡或反流性食管炎，未发现相关诊断或病史支持"

    return submit_result(
        is_applicable=True,
        is_compliant=compliant,
        failure_message=fail_msg,
        evidence={
            "summary": {
                "matched_drug": get_val(target_items, "药品通用名"),
                "icd_evidence": get_val(matched_icd, "ICD编码"),
                "name_evidence": get_val(matched_names, "诊断名称"),
                "ai_result": has_ai_evidence,
            },
            "highlights": [
                {"field_path": "$.用药信息.药品通用名", "highlighted_text": str(name)}
                for name in get_val(target_items, "药品通用名", default=[])
            ] + [
                {"field_path": "$.诊断信息.ICD编码", "highlighted_text": str(code)}
                for code in get_val(matched_icd, "ICD编码", default=[])
            ] + [
                {"field_path": "$.诊断信息.诊断名称", "highlighted_text": str(name)}
                for name in get_val(matched_names, "诊断名称", default=[])
            ],
        },
    )

Example Input: "静脉注射与静脉采血不能同时开"
Example Output:
def execute_rule(ctx):
    fees = get_val(ctx, "收费报告", default=[])
    injection_items = filter_list(fees, "收费项目名称", "静脉注射", "contains")
    blood_collection_items = filter_list(fees, "收费项目名称", "静脉采血", "contains")

    time_grouped_injections = {}
    time_grouped_collections = {}

    for item in injection_items:
        charge_time = get_val(item, "收费日期", "")
        if charge_time:
            time_key = charge_time[:19]
            time_grouped_injections.setdefault(time_key, []).append(item)

    for item in blood_collection_items:
        charge_time = get_val(item, "收费日期", "")
        if charge_time:
            time_key = charge_time[:19]
            time_grouped_collections.setdefault(time_key, []).append(item)

    conflict_times = []
    for time_key in time_grouped_injections:
        if time_key in time_grouped_collections:
            conflict_times.append({
                "time": time_key,
                "injection_count": len(time_grouped_injections[time_key]),
                "blood_collection_count": len(time_grouped_collections[time_key]),
            })

    is_target = len(injection_items) > 0 or len(blood_collection_items) > 0
    compliant = len(conflict_times) == 0
    fail_msg = ""
    if is_target and not compliant:
        fail_msg = f"静脉注射与静脉采血在同一时间同时开具，冲突时间点：{conflict_times}"

    return submit_result(
        is_applicable=is_target,
        is_compliant=compliant,
        failure_message=fail_msg,
        evidence={
            "summary": {
                "total_injection_count": len(injection_items),
                "total_blood_collection_count": len(blood_collection_items),
                "conflict_times": conflict_times,
            },
            "highlights": [
                {"field_path": "$.收费报告.收费项目名称", "highlighted_text": str(get_val(item, "收费项目名称", ""))}
                for item in injection_items + blood_collection_items
            ],
        },
    )

Example Input: "糖化血红蛋白测定 原价13元 在糖化血红蛋白测定基础上免疫化学法加收10元，色谱法加收15元，如果费用超过标准，则违规，如果有加收项目但没有基础项目也违规"
Example Output:
def execute_rule(ctx):
    fee_reports = get_val(ctx, "收费报告", default=[])
    base_items = filter_list(fee_reports, "收费项目名称", "糖化血红蛋白测定", "==")
    related_items = filter_list(fee_reports, "收费项目名称", "糖化血红蛋白测定", "contains")
    additional_items = filter_list(related_items, "收费项目名称", ["免疫化学法", "色谱法"], "contains")

    is_target = len(additional_items) > 0
    applicable = is_target
    compliant = False
    fail_msg = ""
    has_missing_base_fee = False
    has_base_fee_error = False
    has_additional_fee_error = False
    missing_base_fee_details = []
    base_fee_error_details = []
    additional_fee_error_details = []

    if applicable:
        if len(base_items) == 0:
            has_missing_base_fee = True
            missing_base_fee_details = [{"违规类型": "缺少基础项目", "要求": "必须先收取糖化血红蛋白测定13元，才能收取加收项目"}]
        else:
            incorrect_base_fee_items = []
            for item in base_items:
                item_fee = get_val(item, "项目单价", default=0)
                item_name = get_val(item, "收费项目名称", default="")
                if is_compare(value=item_fee, operator=">", threshold=13):
                    incorrect_base_fee_items.append({"项目名称": item_name, "项目单价": item_fee})
            if len(incorrect_base_fee_items) > 0:
                has_base_fee_error = True
                base_fee_error_details = [{"违规类型": "基础项目费用错误", "要求": "基础项目应为13元", "实际收费": incorrect_base_fee_items}]

        for item in additional_items:
            item_fee = get_val(item, "项目单价", default=0)
            item_name = get_val(item, "收费项目名称", default="未知项目")
            expected_fee = 0
            item_type = ""
            if "免疫化学法" in item_name:
                expected_fee = 10
                item_type = "免疫化学法加收"
            elif "色谱法" in item_name:
                expected_fee = 15
                item_type = "色谱法加收"
            if expected_fee and is_compare(value=item_fee, operator=">", threshold=expected_fee):
                has_additional_fee_error = True
                additional_fee_error_details.append({"项目名称": item_name, "项目类型": item_type, "实际收费": item_fee, "期望收费": expected_fee})

        compliant = not has_missing_base_fee and not has_base_fee_error and not has_additional_fee_error
        if not compliant:
            violation_details = []
            if has_missing_base_fee:
                violation_details.append("缺少基础糖化血红蛋白测定项目")
            if has_base_fee_error:
                violation_details.append("基础项目费用错误")
            if has_additional_fee_error:
                violation_details.append(f"加收项目费用错误: {additional_fee_error_details}")
            fail_msg = " | ".join(violation_details)

    return submit_result(
        is_applicable=applicable,
        is_compliant=compliant,
        failure_message=fail_msg,
        evidence={
            "summary": {
                "目标项目数": len(additional_items),
                "基础项目数": len(base_items),
                "基础项目费用错误": has_base_fee_error,
                "加收项目费用错误": has_additional_fee_error,
                "缺少基础项目": has_missing_base_fee,
            },
            "highlights": [
                {"field_path": "$.收费报告.收费项目名称", "highlighted_text": str(get_val(item, "收费项目名称", ""))}
                for item in base_items + additional_items
            ] + [
                {"field_path": "$.收费报告.项目单价", "highlighted_text": str(get_val(item, "项目单价", ""))}
                for item in base_items + additional_items
            ],
            "items": {
                "基础项目错误详情": base_fee_error_details,
                "加收项目错误详情": additional_fee_error_details,
                "缺少基础项目详情": missing_base_fee_details,
            },
        },
    )
'''.strip()


def json_data_schema() -> str:
    return """
{
  "收费报告": [
    {
      "住院号": "xxx",
      "收费项目名称": "xxx",
      "收费项目代码": "xxx",
      "收费日期": "xxx",
      "项目数量": "xxx",
      "项目单价": "xxx",
      "项目单位": "xxx",
      "项目费用": "xxx",
      "费用类别": "xxx",
      "ORDER_NO": "xxx",
      "ORDER_ITEM_CODE": "xxx"
    }
  ],
  "用药信息": [
    {
      "药品通用名": "xxx",
      "药品名称": "xxx",
      "药品编码": "xxx",
      "医嘱开始时间": "xxx",
      "医嘱结束时间": "xxx",
      "剂量": "xxx",
      "频次": "xxx"
    }
  ],
  "诊断信息": [
    {
      "诊断名称": "xxx",
      "ICD编码": "xxx",
      "主诊断标志": "xxx"
    }
  ],
  "入院记录": {
    "现病史": "xxx",
    "既往史": "xxx",
    "初步诊断": "xxx"
  },
  "首次病程记录": {
    "文档内容": "xxx"
  }
}
""".strip()
