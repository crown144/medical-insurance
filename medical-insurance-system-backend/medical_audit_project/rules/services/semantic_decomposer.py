from __future__ import annotations

import json
import re
from typing import Any


SYSTEM_PROMPT = """You decompose an insurance rule IRR into atomic constraints and Boolean logic.

Return JSON only with two top-level fields: atomic_constraints and logic_tree.
Do not generate Python, EMR field names, audit functions, or execution bindings.
Decompose only Constraint Condition. Constraint Object is the audited object and is handled
separately as applicability scope. Do not create an atom merely to represent use, ordering,
or charging of Constraint Object, even when the condition sentence repeats its name.

Each atomic constraint must contain:
- id: stable sequential IDs A1, A2, A3, ...
- normalized_constraint: a concise English statement
- source_span: an exact excerpt from the original Constraint Condition; Chinese is allowed here

The logic tree must use only nested and/or/not objects and atomic IDs. The tree represents the
conditions under which the rule is compliant. Preserve branches, parentheses, and negation.
AND and OR values must be non-empty arrays. NOT must contain exactly one operand.
Split independently testable facts into separate atoms.
Never combine an age requirement with a diagnosis in one atom. Never combine a diagnosis,
disease stage, and prior-treatment status in one atom. An inclusive/exclusive age range may
remain one atom, but clinical status and treatment-history requirements must be separate atoms.
Represent negation in the logic tree; atomic constraints should describe positive testable facts whenever possible.
"""


SUPPORTED_FALLBACK_OBJECTS = (
    ('ilaprazole', '艾普拉唑'),
    ('calcium acetate', '醋酸钙'),
    ('intravenous injection', '静脉注射'),
    ('arterial pressure injection', '动脉加压注射'),
    ('entecavir oral solution', '恩替卡韦口服溶液'),
)


def build_messages(irr: dict[str, str]) -> list[dict[str, str]]:
    return [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        {
            'role': 'user',
            'content': json.dumps({'irr': irr}, ensure_ascii=False),
        },
    ]


def has_supported_fallback(irr: dict[str, str]) -> bool:
    object_text = irr.get('constraint_object', '').lower()
    return any(
        any(alias.lower() in object_text for alias in aliases)
        for aliases in SUPPORTED_FALLBACK_OBJECTS
    )


def parse_decomposition(raw_output: str) -> dict[str, Any]:
    text = (raw_output or '').strip()
    fenced = re.search(r'```(?:json)?\s*(.*?)```', text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    if not text.startswith('{'):
        start = text.find('{')
        end = text.rfind('}')
        if start >= 0 and end > start:
            text = text[start:end + 1]
    return validate_decomposition(json.loads(text))


def validate_decomposition(value: dict[str, Any]) -> dict[str, Any]:
    atoms = value.get('atomic_constraints')
    logic = _normalize_logic_tree(value.get('logic_tree'))
    if not isinstance(atoms, list) or not atoms:
        raise ValueError('Semantic decomposition must contain atomic_constraints.')

    ids: list[str] = []
    normalized_atoms: list[dict[str, str]] = []
    for index, atom in enumerate(atoms, start=1):
        if not isinstance(atom, dict):
            raise ValueError('Each atomic constraint must be an object.')
        atom_id = str(atom.get('id') or '').strip()
        expected_id = f'A{index}'
        if atom_id != expected_id:
            raise ValueError(f'Atomic constraint IDs must be sequential; expected {expected_id}.')
        normalized = str(atom.get('normalized_constraint') or '').strip()
        source_span = str(atom.get('source_span') or '').strip()
        if not normalized or not source_span:
            raise ValueError(f'{atom_id} must include normalized_constraint and source_span.')
        if re.search(r'[\u4e00-\u9fff]', normalized):
            raise ValueError(f'{atom_id} normalized_constraint must be in English.')
        ids.append(atom_id)
        normalized_atoms.append({
            'id': atom_id,
            'normalized_constraint': normalized,
            'source_span': source_span,
        })

    if len(ids) != len(set(ids)):
        raise ValueError('Atomic constraint IDs must be unique.')

    references: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, str):
            if node not in ids:
                raise ValueError(f'Logic tree references unknown atom {node}.')
            references.append(node)
            return
        if not isinstance(node, dict) or len(node) != 1:
            raise ValueError('Invalid logic node.')
        operator, operands = next(iter(node.items()))
        if operator not in {'and', 'or', 'not'}:
            raise ValueError(f'Unsupported logic operator {operator}.')
        if not isinstance(operands, list) or not operands:
            raise ValueError(f'{operator.upper()} requires at least one operand.')
        if operator == 'not' and len(operands) != 1:
            raise ValueError('NOT requires exactly one operand.')
        for operand in operands:
            walk(operand)

    walk(logic)
    unused = set(ids) - set(references)
    if unused:
        raise ValueError(f'Logic tree does not reference: {", ".join(sorted(unused))}.')
    return {'atomic_constraints': normalized_atoms, 'logic_tree': logic}


def _normalize_logic_tree(node: Any) -> Any:
    """Normalize common structured atom references without changing semantics."""
    if isinstance(node, str):
        return node.strip()
    if not isinstance(node, dict):
        return node

    for reference_key in ('id', 'ref', 'atom', 'atom_id'):
        if set(node) == {reference_key} and isinstance(node[reference_key], str):
            return node[reference_key].strip()

    if len(node) != 1:
        return node
    operator, operands = next(iter(node.items()))
    normalized_operator = str(operator).lower()
    if normalized_operator not in {'and', 'or', 'not'} or not isinstance(operands, list):
        return node
    return {
        normalized_operator: [
            _normalize_logic_tree(operand) for operand in operands
        ],
    }


def render_logic_expression(node: Any, parent_operator: str | None = None) -> str:
    if isinstance(node, str):
        return node
    operator, operands = next(iter(node.items()))
    if operator == 'not':
        child = render_logic_expression(operands[0], operator)
        if isinstance(operands[0], dict):
            child = f'({child})'
        return f'NOT {child}'

    rendered = f' {operator.upper()} '.join(
        render_logic_expression(operand, operator) for operand in operands
    )
    if parent_operator and parent_operator != operator:
        return f'({rendered})'
    return rendered


def ground_source_spans(
    atomic_constraints: list[dict[str, str]],
    constraint_condition: str,
) -> list[dict[str, str]]:
    """Keep exact model spans, otherwise fall back to the authoritative Rule text."""
    grounded = []
    for atom in atomic_constraints:
        source_span = atom.get('source_span', '').strip()
        grounded.append({
            **atom,
            'source_span': (
                source_span
                if source_span and source_span in constraint_condition
                else constraint_condition
            ),
        })
    return grounded


def expand_supported_compound_atoms(value: dict[str, Any]) -> dict[str, Any]:
    """Deterministically split known compound facts before execution binding."""
    original_atoms = value['atomic_constraints']
    replacements: dict[str, list[str]] = {}
    expanded_atoms: list[dict[str, str]] = []

    for atom in original_atoms:
        normalized = atom['normalized_constraint'].lower()
        source_span = atom['source_span']
        parts: list[str]
        if (
            'adult' in normalized
            and ('chronic hepatitis b' in normalized or 'chronic hbv' in normalized)
        ):
            parts = [
                'The patient is an adult.',
                'The patient has chronic hepatitis B.',
            ]
        elif (
            ('chronic hepatitis b' in normalized or 'chronic hbv' in normalized)
            and 'compensated' in normalized
            and ('liver' in normalized or 'hepatic' in normalized)
        ):
            parts = [
                'The patient has chronic HBV infection.',
                'The patient has compensated liver disease.',
            ]
        else:
            parts = [atom['normalized_constraint']]

        new_ids = []
        for part in parts:
            new_id = f'A{len(expanded_atoms) + 1}'
            expanded_atoms.append({
                'id': new_id,
                'normalized_constraint': part,
                'source_span': source_span,
            })
            new_ids.append(new_id)
        replacements[atom['id']] = new_ids

    def replace_logic(node: Any) -> Any:
        if isinstance(node, str):
            ids = replacements[node]
            return ids[0] if len(ids) == 1 else {'and': ids}

        operator, operands = next(iter(node.items()))
        replaced = [replace_logic(operand) for operand in operands]
        if operator in {'and', 'or'}:
            flattened = []
            for operand in replaced:
                if isinstance(operand, dict) and set(operand) == {operator}:
                    flattened.extend(operand[operator])
                else:
                    flattened.append(operand)
            replaced = flattened
        return {operator: replaced}

    expanded = {
        'atomic_constraints': expanded_atoms,
        'logic_tree': replace_logic(value['logic_tree']),
    }
    return validate_decomposition(expanded)


def fallback_decomposition(irr: dict[str, str]) -> dict[str, Any]:
    """Deterministic development fallback for the four existing compilation demo rules."""
    condition = irr.get('constraint_condition', '')
    source = condition
    lowered = f"{irr.get('constraint_object', '')} {condition}".lower()

    if '艾普拉唑' in lowered or 'ilaprazole' in lowered:
        atoms = [
            {'id': 'A1', 'normalized_constraint': 'The patient has a diagnosis of duodenal ulcer.', 'source_span': source},
            {'id': 'A2', 'normalized_constraint': 'The patient has a diagnosis of reflux esophagitis.', 'source_span': source},
        ]
        logic = {'or': ['A1', 'A2']}
    elif '醋酸钙' in lowered or 'calcium acetate' in lowered:
        atoms = [
            {'id': 'A1', 'normalized_constraint': 'The patient has a diagnosis of hyperphosphatemia.', 'source_span': source},
        ]
        logic = 'A1'
    elif '静脉注射' in lowered or 'intravenous injection' in lowered:
        atoms = [
            {'id': 'A1', 'normalized_constraint': 'A venous blood collection is charged at the same time.', 'source_span': source},
        ]
        logic = {'not': ['A1']}
    elif '动脉加压注射' in lowered or 'arterial pressure injection' in lowered:
        atoms = [
            {'id': 'A1', 'normalized_constraint': 'An arterial blood collection is charged at the same time.', 'source_span': source},
        ]
        logic = {'not': ['A1']}
    elif '恩替卡韦口服溶液' in lowered or 'entecavir oral solution' in lowered:
        atoms = [
            {'id': 'A1', 'normalized_constraint': 'The patient is an adult.', 'source_span': source},
            {'id': 'A2', 'normalized_constraint': 'The patient has chronic hepatitis B.', 'source_span': source},
            {'id': 'A3', 'normalized_constraint': 'The patient is aged 2 to under 18 years.', 'source_span': source},
            {'id': 'A4', 'normalized_constraint': 'The patient has chronic HBV infection.', 'source_span': source},
            {'id': 'A5', 'normalized_constraint': 'The patient has compensated liver disease.', 'source_span': source},
            {'id': 'A6', 'normalized_constraint': 'The pediatric patient is nucleoside-treatment-naive.', 'source_span': source},
        ]
        logic = {
            'or': [
                {'and': ['A1', 'A2']},
                {'and': ['A3', 'A4', 'A5', 'A6']},
            ],
        }
    else:
        atoms = [{
            'id': 'A1',
            'normalized_constraint': 'The rule condition is satisfied.',
            'source_span': source,
        }]
        logic = 'A1'
    return validate_decomposition({'atomic_constraints': atoms, 'logic_tree': logic})
