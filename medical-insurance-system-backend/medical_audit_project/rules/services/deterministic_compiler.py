from __future__ import annotations

import ast
from typing import Any


APPROVED_CALLS = {
    'get_val', 'filter_list', 'is_compare', 'llm_bool',
    'submit_result', 'any', 'len', 'str',
}


def compile_rule(
    logic_tree: dict[str, Any] | str,
    applicability_binding: dict[str, Any],
    constraint_bindings: list[dict[str, Any]],
) -> str:
    if applicability_binding.get('status') != 'bound':
        raise ValueError('Constraint Object has no approved applicability binding.')
    unbound = [
        item['atomic_constraint_id']
        for item in constraint_bindings
        if item['status'] != 'bound'
    ]
    if unbound:
        raise ValueError(f"Unbound atomic constraints: {', '.join(unbound)}")

    applicability_runtime = applicability_binding['runtime']
    lines = [
        'def execute_rule(ctx):',
        f"    applicability_records = get_val(ctx, {applicability_runtime['source_path']!r}, default=[])",
        '    applicability_matches = filter_list(',
        '        applicability_records,',
        f"        {applicability_runtime['field_path']!r},",
        f"        {applicability_runtime['match_values']!r},",
        "        'contains',",
        '    )',
        '    is_applicable = len(applicability_matches) > 0',
        '',
    ]

    for binding in constraint_bindings:
        atom_id = binding['atomic_constraint_id']
        variable = atom_id.lower()
        runtime = binding['runtime']
        mode = runtime.get('mode', 'list_filter')
        if mode == 'numeric_comparison':
            comparisons = ' and '.join(
                f"is_compare(value, {operator!r}, {threshold!r})"
                for operator, threshold in runtime['comparisons']
            )
            lines.extend([
                f"    {variable}_values = get_val(ctx, {runtime['source_path']!r} + '.' + {runtime['field_path']!r}, default=[])",
                f"    {atom_id} = any({comparisons} for value in {variable}_values)",
                '',
            ])
            continue
        if mode == 'llm_bool':
            lines.append(f"    {variable}_context_parts = [")
            for path in runtime['context_paths']:
                lines.append(f"        str(get_val(ctx, {path!r}, default='')),")
            lines.extend([
                '    ]',
                f"    {variable}_context = ' '.join({variable}_context_parts)",
                f"    {atom_id} = llm_bool(",
                f"        context_text={variable}_context,",
                f"        question={runtime['question']!r},",
                '    )',
                '',
            ])
            continue

        source_paths = runtime.get('source_paths') or [runtime['source_path']]
        lines.append(f"    {variable}_records = []")
        for source_path in source_paths:
            lines.append(
                f"    {variable}_records += get_val(ctx, {source_path!r}, default=[])"
            )
        lines.extend([
            f"    {variable}_matches = filter_list(",
            f"        {variable}_records,",
            f"        {runtime['field_path']!r},",
            f"        {runtime['match_values']!r},",
            "        'contains',",
            '    )',
        ])
        if runtime.get('relation') == 'same_time_with_applicability':
            time_field = runtime['time_field']
            lines.extend([
                f"    applicability_times = [get_val(item, {time_field!r}, default='') for item in applicability_matches]",
                f"    {variable}_times = [get_val(item, {time_field!r}, default='') for item in {variable}_matches]",
                f"    {atom_id} = any(value and value in applicability_times for value in {variable}_times)",
                '',
            ])
        else:
            lines.extend([f"    {atom_id} = len({variable}_matches) > 0", ''])

    condition_expression = _compile_logic(logic_tree)
    failure_checks = _build_failure_checks(logic_tree, constraint_bindings)
    atom_pairs = ', '.join(
        f"{item['atomic_constraint_id']!r}: {item['atomic_constraint_id']}"
        for item in constraint_bindings
    )
    lines.extend([
        f'    condition_satisfied = {condition_expression}',
        '    is_compliant = condition_satisfied if is_applicable else True',
        '    failed_conditions = []',
    ])
    for condition, message in failure_checks:
        lines.extend([
            f'    if {condition}:',
            f'        failed_conditions += [{message!r}]',
        ])
    lines.extend([
        "    failure_message = ''",
        '    if is_applicable and not condition_satisfied:',
        '        if failed_conditions:',
        "            failure_message = 'Rule violation. ' + '; '.join(failed_conditions)",
        '        else:',
        f"            failure_message = {'Rule violation. Logical expression was not satisfied: ' + condition_expression!r}",
        '    return submit_result(',
        '        is_applicable=is_applicable,',
        '        is_compliant=is_compliant,',
        '        failure_message=failure_message,',
        "        evidence={",
        "            'applicability_matched': is_applicable,",
        f"            'atomic_results': {{{atom_pairs}}},",
        "            'highlights': [],",
        '        },',
        '    )',
    ])
    code = '\n'.join(lines)
    validation = validate_generated_code(code)
    if not validation['valid']:
        raise ValueError('; '.join(validation['errors']))
    return code


def _build_failure_checks(
    logic_tree: dict[str, Any] | str,
    constraint_bindings: list[dict[str, Any]],
) -> list[tuple[str, str]]:
    polarities: dict[str, set[bool]] = {}

    def walk(node: Any, negated: bool = False) -> None:
        if isinstance(node, str):
            polarities.setdefault(node, set()).add(negated)
            return
        operator, operands = next(iter(node.items()))
        for operand in operands:
            walk(operand, not negated if operator == 'not' else negated)

    walk(logic_tree)
    checks = []
    for binding in constraint_bindings:
        atom_id = binding['atomic_constraint_id']
        description = str(
            binding.get('normalized_constraint') or atom_id
        ).strip().rstrip('.')
        for negated in sorted(polarities.get(atom_id, {False})):
            if negated:
                checks.append((
                    atom_id,
                    f'{atom_id} must be absent but was present: {description}',
                ))
            else:
                checks.append((
                    f'not {atom_id}',
                    f'{atom_id} not satisfied: {description}',
                ))
    return checks


def _compile_logic(node: Any) -> str:
    if isinstance(node, str):
        return node
    operator, operands = next(iter(node.items()))
    if operator == 'not':
        return f'(not {_compile_logic(operands[0])})'
    token = ' and ' if operator == 'and' else ' or '
    return '(' + token.join(_compile_logic(operand) for operand in operands) + ')'


def validate_generated_code(code: str) -> dict[str, Any]:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return {'valid': False, 'errors': [str(exc)]}

    errors: list[str] = []
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    execute = next((node for node in functions if node.name == 'execute_rule'), None)
    if execute is None or len(execute.args.args) != 1 or execute.args.args[0].arg != 'ctx':
        errors.append('missing execute_rule(ctx) entrypoint')
    elif not any(
        isinstance(node, ast.Return)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == 'submit_result'
        for node in ast.walk(execute)
    ):
        errors.append('missing return submit_result(...)')
    if any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(tree)):
        errors.append('imports are not allowed')
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    unknown = sorted(calls - APPROVED_CALLS)
    if unknown:
        errors.append(f"unapproved function calls: {', '.join(unknown)}")
    return {'valid': not errors, 'errors': errors}
