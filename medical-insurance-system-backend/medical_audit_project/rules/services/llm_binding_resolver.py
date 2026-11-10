from __future__ import annotations

import json
import re
from typing import Any

from .binding_resolver import CATEGORY_STRATEGIES
from .capability_catalog import CAPABILITY_CATALOG, public_catalog


BINDING_SYSTEM_PROMPT = """你是医保审核规则的执行绑定器。你的任务是将已经分解的原子约束绑定到系统提供的审核能力。
你只能选择 Available Capabilities 中存在的 capability_id，并填写该能力 parameter_schema 允许的参数。
你不能生成 Python，不能创造病历字段、函数或能力，不能输出 data_source、field、function 或 runtime，不能修改原子约束和逻辑树。
Applicability Binding 必须只依据 Rule Category 和 Constraint Object；Constraint Bindings 必须逐一对应 Atomic Constraints。
如果没有能力能够可靠执行某个原子约束，必须返回 unbound。所有阈值、范围、匹配值和问题必须能从 normalized_constraint、source_span 或 Constraint Object 中追溯得到。
normalized_constraint、capability_id、参数值以及 JSON key 保持输入规定的语言和格式。只输出 JSON，不要输出 Markdown 或额外解释。"""


REQUIRED_OUTPUT_SCHEMA = {
    'type': 'object',
    'required': ['applicability_binding', 'constraint_bindings'],
    'properties': {
        'applicability_binding': {
            'oneOf': [
                {
                    'status': 'bound',
                    'capability_id': '<available applicability capability_id>',
                    'parameters': '<object matching parameter_schema>',
                    'source_reference': {
                        'type': 'constraint_object',
                        'text': '<exact Constraint Object>',
                    },
                },
                {'status': 'unbound', 'reason': '<specific reason>'},
            ],
        },
        'constraint_bindings': [{
            'atomic_id': '<exact Atomic Constraint ID>',
            'status': 'bound | unbound',
            'capability_id': '<required only when bound>',
            'parameters': '<required only when bound>',
            'source_span': '<exact atom source_span>',
            'reason': '<required only when unbound>',
        }],
    },
}


BINDING_EXAMPLES = [
    {
        'input': {
            'constraint_object': 'Entecavir Oral Solution',
            'atomic_constraint': {
                'id': 'A1',
                'normalized_constraint': 'The patient is an adult.',
                'source_span': 'adult patients',
            },
        },
        'output': {
            'applicability_binding': {
                'status': 'bound',
                'capability_id': 'medication_name_matching',
                'parameters': {
                    'operator': 'contains',
                    'match_values': ['恩替卡韦口服溶液', 'Entecavir Oral Solution'],
                },
                'source_reference': {
                    'type': 'constraint_object',
                    'text': 'Entecavir Oral Solution',
                },
            },
            'constraint_bindings': [{
                'atomic_id': 'A1',
                'status': 'bound',
                'capability_id': 'age_comparison',
                'parameters': {'operator': '>=', 'threshold': 18},
                'source_span': 'adult patients',
            }],
        },
    },
    {
        'input': {
            'atomic_constraint': {
                'id': 'A9',
                'normalized_constraint': 'The patient satisfies an unsupported genomic condition.',
                'source_span': 'genomic condition',
            },
        },
        'output': {
            'atomic_id': 'A9',
            'status': 'unbound',
            'reason': 'No approved capability can evaluate this condition.',
            'source_span': 'genomic condition',
        },
    },
]


def request_binding_plan(
    client: Any,
    model: str,
    irr: dict[str, str],
    atomic_constraints: list[dict[str, str]],
    logic_tree: dict[str, Any] | str,
    *,
    max_tokens: int,
) -> dict[str, Any]:
    response = client.chat.completions.create(
        model=model,
        messages=build_binding_messages(irr, atomic_constraints, logic_tree),
        temperature=0,
        max_tokens=max_tokens,
        response_format={'type': 'json_object'},
        extra_body={'enable_thinking': False},
    )
    raw_output = response.choices[0].message.content or ''
    return parse_binding_output(raw_output)


def build_binding_messages(
    irr: dict[str, str],
    atomic_constraints: list[dict[str, str]],
    logic_tree: dict[str, Any] | str,
) -> list[dict[str, str]]:
    candidate_ids = select_candidate_capabilities(irr, atomic_constraints)
    payload = {
        'IRR': irr,
        'Atomic Constraints': atomic_constraints,
        'Logic Tree': logic_tree,
        'Available Capabilities': public_catalog(candidate_ids),
        'Required JSON Schema': REQUIRED_OUTPUT_SCHEMA,
        'Binding Examples': BINDING_EXAMPLES,
    }
    return [
        {'role': 'system', 'content': BINDING_SYSTEM_PROMPT},
        {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)},
    ]


def select_candidate_capabilities(
    irr: dict[str, str],
    atomic_constraints: list[dict[str, str]],
) -> list[str]:
    selected: set[str] = set()
    strategy = CATEGORY_STRATEGIES.get(irr.get('rule_category', '').strip())
    if strategy:
        selected.update(strategy['capability_ids'])

    text = ' '.join(
        f"{atom.get('normalized_constraint', '')} {atom.get('source_span', '')}"
        for atom in atomic_constraints
    ).lower()
    if any(token in text for token in ('age', 'aged', 'year', 'adult', '岁')):
        selected.update({'age_comparison', 'age_range'})
    if any(token in text for token in (
        'diagnosis', 'disease', 'hepatitis', 'hbv', 'ulcer',
        'esophagitis', 'hyperphosphatemia', '诊断', '肝炎', '溃疡',
    )):
        selected.update({'diagnosis_name_matching', 'list_membership'})
    if any(token in text for token in (
        'charge', 'charged', 'injection', 'collection', 'billing',
        '收费', '注射', '采血',
    )):
        selected.add('charge_record_filtering')
    if any(token in text for token in (
        'history', 'documented', 'compensated', 'naive',
        '病史', '代偿', '初治',
    )):
        selected.add('clinical_text_semantic_assessment')
    if any(token in text for token in (
        'amount', 'quantity', 'total', 'average', 'maximum', 'minimum',
        '金额', '数量', '总计', '平均',
    )):
        selected.update({'numeric_comparison', 'statistical_calculation'})
    if any(token in text for token in (
        'interval', 'gap', 'span', 'days apart', 'frequency',
        '间隔', '跨度', '相隔', '频次',
    )):
        selected.add('temporal_interval_calculation')

    # A small catalog makes a conservative fallback candidate set affordable,
    # while still excluding applicability-only capabilities from constraints.
    if not any(
        item != 'medication_name_matching' for item in selected
    ):
        selected.update({
            capability_id
            for capability_id, capability in CAPABILITY_CATALOG.items()
            if 'constraint' in capability.get('roles', [])
        })
    return sorted(selected)


def parse_binding_output(raw_output: str) -> dict[str, Any]:
    text = (raw_output or '').strip()
    fenced = re.search(r'```(?:json)?\s*(.*?)```', text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    if not text.startswith('{'):
        start = text.find('{')
        end = text.rfind('}')
        if start >= 0 and end > start:
            text = text[start:end + 1]
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError('Binding LLM output must be a JSON object.')
    return value

