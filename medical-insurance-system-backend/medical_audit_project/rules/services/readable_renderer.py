"""Deterministic, non-executable explanation of a compiled execution plan."""
from __future__ import annotations

import ast
from pprint import pformat
from textwrap import wrap
from typing import Any


def compiled_plan_from_code(code: str) -> dict[str, Any]:
    """Read the literal plan from the actual generated execution program."""
    tree = ast.parse(code)
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name == 'execute_rule']
    if len(functions) != 1:
        raise ValueError('Generated program has no unique execution entrypoint.')
    calls = [node for node in ast.walk(functions[0]) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id == 'execute_compiled_plan']
    if len(calls) != 1 or len(calls[0].args) != 2:
        raise ValueError('Generated program has no unique compiled plan.')
    plan = ast.literal_eval(calls[0].args[1])
    if not isinstance(plan, dict) or not {'logic', 'applicability', 'constraints'} <= plan.keys():
        raise ValueError('Generated program contains an invalid compiled plan.')
    return plan


def render_readable_python(compiled_plan: dict[str, Any]) -> str:
    """Render a Python-syntax preview; conceptual helpers are not executable APIs.

    The execution plan remains authoritative. Lambdas express deferred execution;
    the real executor handles three-state logic, branch selection and evidence.
    """
    bindings = {item['atomic_constraint_id']: item for item in compiled_plan['constraints']}
    names = {atom_id: f'check_atom_{index}' for index, atom_id in enumerate(bindings, 1)}
    lines = [
        '# Executable logic preview (conceptual helpers; not a standalone program).',
        '# The execution plan controls short-circuiting and evidence handling.',
        '',
        'def execute_rule_preview(ctx):',
    ]

    def literal(value: Any, indent: str) -> None:
        parts = pformat(value, width=68, sort_dicts=False).splitlines()
        lines.extend(indent + part for part in parts)

    def emit_check(name: str, binding: dict[str, Any], atom_id: str | None) -> None:
        runtime = binding.get('runtime') or {}
        sources = binding.get('evidence_sources') or runtime.get('evidence_sources')
        if sources is None:
            paths = runtime.get('context_paths')
            if paths is None:
                roots = runtime.get('source_paths') or [runtime.get('source_path')]
                paths = [f"{root}.{runtime['field_path']}" for root in roots
                         if root and runtime.get('field_path')]
            sources = [{'path': path} for path in paths]
        helper = 'assess_text_evidence' if runtime.get('mode') == 'llm_bool' else 'check_evidence'
        description = binding.get('normalized_constraint')
        if description and atom_id is not None:
            for part in wrap(str(description), width=70, replace_whitespace=True):
                lines.append(f'    # {atom_id}: {part}')
        lines.append(f'    def {name}():')
        lines.append(f'        return {helper}(')
        lines.append('            ctx,')
        if atom_id is not None:
            lines.append(f'            atomic_id={atom_id!r},')
        lines.append(f"            audit_function={binding.get('audit_function')!r},")
        lines.append('            evidence_sources=[')
        for source in sources:
            literal(source, '                ')
            lines[-1] += ','
        lines.append('            ],')
        runtime_display = {key: value for key, value in runtime.items()
                           if key not in {'evidence_sources', 'context_paths'}}
        runtime_lines = pformat(runtime_display, width=68, sort_dicts=False).splitlines()
        lines.append('            runtime=' + runtime_lines[0])
        lines.extend('            ' + part for part in runtime_lines[1:])
        lines[-1] += ','
        lines.append('        )')
        lines.append('')

    emit_check('check_applicability', compiled_plan['applicability'], None)
    for atom_id, binding in bindings.items():
        emit_check(names[atom_id], binding, atom_id)

    def cost(node: Any) -> int:
        if isinstance(node, str):
            return int((bindings[node].get('runtime') or {}).get('mode') == 'llm_bool')
        return max((cost(child) for child in next(iter(node.values()))), default=0)

    def emit_logic(node: Any, indent: str, prefix: str = '') -> None:
        if isinstance(node, str):
            lines.append(f'{indent}{prefix}{names[node]}(),  # {node}')
            return
        operator, children = next(iter(node.items()))
        helper = {'and': 'lazy_all', 'or': 'lazy_any', 'not': 'logical_not'}[operator]
        lines.append(f'{indent}{prefix}{helper}(')
        for index, child in sorted(enumerate(children), key=lambda pair: cost(pair[1])):
            if operator == 'or':
                lines.append(f'{indent}    # Alternative branch {index + 1}')
            emit_logic(child, indent + '    ', 'lambda: ')
        lines.append(f'{indent}),')

    lines.extend([
        '    applicability = check_applicability()',
        '    if applicability.is_not_applicable:',
        '        return not_applicable(applicability)',
        '    if applicability.insufficient_evidence:',
        '        return needs_review(applicability)',
        '',
        '    decision = evaluate_logic(',
    ])
    emit_logic(compiled_plan['logic'], '        ', 'lambda: ')
    lines.extend([
        '    )',
        '    return finalize_decision(applicability, decision)',
    ])
    preview = '\n'.join(lines) + '\n'
    ast.parse(preview)
    return preview
