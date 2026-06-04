from __future__ import annotations

import ast
import os
from dataclasses import dataclass
from typing import Any

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


class AgentAService:
    """系统内自包含的规则编译服务，默认调用阿里云百炼 Qwen3.5。"""

    @classmethod
    def _llm_config(cls) -> dict[str, Any]:
        return {
            'base_url': os.environ.get('AGENTA_BASE_URL')
            or os.environ.get('DASHSCOPE_BASE_URL')
            or 'https://dashscope.aliyuncs.com/compatible-mode/v1',
            'model': os.environ.get('AGENTA_MODEL')
            or os.environ.get('DASHSCOPE_MODEL')
            or 'qwen3.5-35b-a3b',
            'api_key': os.environ.get('AGENTA_API_KEY')
            or os.environ.get('DASHSCOPE_API_KEY')
            or '',
        }

    @classmethod
    def is_temp_llm_disabled(cls) -> bool:
        return os.environ.get(TEMP_DISABLE_LLM_ENV, '').strip().lower() in {'1', 'true', 'yes', 'on'}

    @classmethod
    def _create_client(cls) -> tuple[OpenAI, str]:
        config = cls._llm_config()
        api_key = config['api_key']
        if not api_key:
            raise ValueError('未配置 AGENTA_API_KEY / DASHSCOPE_API_KEY，请先设置阿里云百炼 API Key')
        client = OpenAI(api_key=api_key, base_url=config['base_url'])
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
        system_prompt = f"""
你是一名医保规则转换专家，负责将自然语言医保规则转换为标准的 Python 审核函数。

要求：
1. 只输出 Python 代码，不要输出解释、markdown、标题。
2. 必须生成 execute_rule(ctx) 函数。
3. 只能使用以下工具函数：{', '.join(tools)}。
4. 输出代码必须能通过 ast.parse 语法检查。
5. 逻辑要尽量简洁、稳定、可执行。
6. 如果规则里有时间限制、范围限制、条件限制，请在代码中体现。

数据结构示例：
{json_data_schema()}
""".strip()

        user_prompt = f'规则文本：{rule_text}\n请直接输出可执行的 Python 规则函数代码。'
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
            max_tokens=2000,
        )

        raw_output = response.choices[0].message.content or ''
        generated_code = cls._clean_code(raw_output)
        validation = cls.validate_code(generated_code)
        snapshot = cls._rule_snapshot(rule_text, generated_code)
        snapshot['runtime_mode'] = 'llm'
        snapshot['runtime_label'] = '大模型生成'
        snapshot['raw_output'] = raw_output
        snapshot['llm_config'] = {
            'base_url': cls._llm_config()['base_url'],
            'model': model,
            'provider': 'aliyun_bailian_qwen',
        }
        return AgentAGenerationResult(
            rule_text=rule_text,
            system_prompt=cls._system_prompt(rule_text),
            tool_schema=tools,
            generated_code=generated_code,
            validation=validation,
            rule_snapshot=snapshot,
            raw_output=raw_output,
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
  ]
}
""".strip()
