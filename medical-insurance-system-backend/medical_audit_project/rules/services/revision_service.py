"""Catalog-constrained, typed revisions for compiled rule drafts."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from .agenta_service import AgentAService, AgentAGenerationResult
from .binding_resolver import (
    _validate_parameters as _catalog_validate_parameters,
    materialize_binding,
)
from .capability_catalog import CAPABILITY_CATALOG, public_catalog
from .deterministic_compiler import compile_rule
from .semantic_decomposer import render_logic_expression


SOURCE_LABELS = {
    '用药信息': 'Medication Records', '诊断': 'Diagnosis Records',
    '医保信息': 'Insurance Information', '入院记录': 'Admission Record',
    '首次病程记录': 'First Progress Note', '收费报告': 'Charge Records',
}
FIELD_LABELS = {
    '药品名': 'Medication Name', '药品通用名': 'Generic Drug Name',
    '药品国家编码': 'National Medication Code', '诊断名称': 'Diagnosis Name',
    'ICD10名称': 'ICD-10 Diagnosis Name', 'ICD10编码': 'ICD-10 Code',
    '年龄': 'Age', '现病史': 'History of Present Illness',
    '既往史': 'Medical History', '文档内容': 'Document Content',
    '收费项目名称': 'Charge Item Name', '项目费用': 'Charge Amount',
    '收费日期': 'Charge Date',
}
SUPPORTED_OPERATIONS = {
    'set_evidence_sources', 'replace_evidence_source', 'add_evidence_source',
    'remove_evidence_source', 'set_parameter', 'set_capability', 'set_logic',
    'add_atom', 'update_atom', 'remove_atom',
}


def _schema() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[4] / 'field.json'
    if not path.is_file():
        raise ValueError('EMR schema field.json is unavailable.')
    return json.loads(path.read_text(encoding='utf-8'))


def _path_exists(path: str) -> bool:
    current: Any = _schema()
    for component in path.split('.'):
        if isinstance(current, list):
            current = current[0] if current else {}
        if not isinstance(current, dict) or component not in current:
            return False
        current = current[component]
    return True


def _default_paths(capability: dict[str, Any]) -> list[str]:
    runtime = capability.get('runtime') or {}
    paths = runtime.get('context_paths')
    if paths is not None:
        return list(paths)
    roots = runtime.get('source_paths') or [runtime.get('source_path')]
    field = runtime.get('field_path')
    return [f'{root}.{field}' for root in roots if root and field]


def _allowed_paths(capability_id: str) -> list[str]:
    capability = CAPABILITY_CATALOG.get(capability_id)
    if not capability:
        return []
    return list(capability.get('allowed_evidence_paths') or _default_paths(capability))


def _source(path: str) -> dict[str, str]:
    source, field = path.rsplit('.', 1)
    return {'data_source': source, 'field': field, 'path': path}


def _set_sources(binding: dict[str, Any], paths: list[str]) -> None:
    if not isinstance(paths, list) or not paths or any(not isinstance(path, str) or '.' not in path for path in paths):
        raise ValueError('Evidence sources must be a non-empty list of physical EMR paths.')
    paths = list(dict.fromkeys(path.strip() for path in paths))
    unknown = [path for path in paths if not _path_exists(path)]
    if unknown:
        raise ValueError('Unknown EMR path: ' + ', '.join(unknown))
    allowed = _allowed_paths(str(binding.get('capability_id') or ''))
    incompatible = [path for path in paths if path not in allowed]
    if incompatible:
        raise ValueError(
            f"{binding.get('capability_id')} cannot use {', '.join(incompatible)}. "
            f"Allowed evidence paths: {', '.join(allowed) or 'none'}."
        )
    sources = [_source(path) for path in paths]
    binding['evidence_sources'] = sources
    binding['source_count'] = len(sources)
    runtime = binding.setdefault('runtime', {})
    runtime['evidence_sources'] = deepcopy(sources)
    if runtime.get('mode') == 'llm_bool':
        runtime['context_paths'] = paths
    if len(sources) == 1:
        source = sources[0]
        binding['data_source'] = SOURCE_LABELS.get(source['data_source'], source['data_source'])
        binding['field'] = FIELD_LABELS.get(source['field'], source['field'])
        binding['logical_label'] = binding['field']
        runtime['source_path'] = source['data_source']
        runtime['field_path'] = source['field']


def canonical_draft(raw: Any, irr: dict[str, str]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError('A structured compilation draft is required.')
    draft = deepcopy(raw)
    draft['irr'] = deepcopy(irr)
    atoms = draft.get('atomic_constraints')
    if not isinstance(atoms, list) or not atoms:
        raise ValueError('The draft must contain atomic constraints.')
    ids = [item.get('id') for item in atoms if isinstance(item, dict)]
    if len(ids) != len(atoms) or any(not isinstance(item, str) or not item for item in ids) or len(set(ids)) != len(ids):
        raise ValueError('Atomic IDs must be unique non-empty strings.')
    for atom in atoms:
        if not atom.get('normalized_constraint'):
            raise ValueError('Each atomic constraint requires a description.')
    bindings = draft.get('constraint_bindings') or []
    if len(bindings) != len(ids) or {item.get('atomic_constraint_id') for item in bindings} != set(ids):
        raise ValueError('Each atomic constraint requires exactly one execution binding.')
    atom_map = {item['id']: item for item in atoms}
    for binding in [draft.get('applicability_binding') or {}, *bindings]:
        capability = CAPABILITY_CATALOG.get(binding.get('capability_id'))
        if not capability or binding.get('audit_function') != capability['function']:
            raise ValueError('An execution binding references an unregistered or incompatible audit function.')
        if not binding.get('runtime'):
            raise ValueError('The draft is missing execution parameters. Recompile the rule first.')
        atom = atom_map.get(binding.get('atomic_constraint_id'))
        if atom:
            binding['normalized_constraint'] = atom['normalized_constraint']
    compile_rule(draft.get('logic_tree'), draft['applicability_binding'], bindings)
    return {key: draft[key] for key in (
        'irr', 'atomic_constraints', 'logic_tree',
        'applicability_binding', 'constraint_bindings',
    )}


def compile_draft(raw: Any, irr: dict[str, str]) -> AgentAGenerationResult:
    draft = canonical_draft(raw, irr)
    app, bindings = draft['applicability_binding'], draft['constraint_bindings']
    code = compile_rule(draft['logic_tree'], app, bindings, atomic_constraints=draft['atomic_constraints'])
    return AgentAGenerationResult(
        rule_text=irr['constraint_condition'], system_prompt={'style': 'confirmed_revision'},
        tool_schema=sorted({item['audit_function'] for item in [app, *bindings]}),
        generated_code=code, validation={'valid': True, 'errors': []},
        rule_snapshot={'runtime_mode': 'confirmed_revision', 'runtime_label': 'Confirmed draft compiled deterministically'},
        irr=draft['irr'], atomic_constraints=draft['atomic_constraints'], logic_tree=draft['logic_tree'],
        logical_expression=render_logic_expression(draft['logic_tree']), applicability_binding=app,
        constraint_bindings=bindings,
        execution_bindings=[{**app, 'atomic_constraint_id': 'Applicability', 'role': 'applicability'},
                            *({**item, 'role': 'condition'} for item in bindings)],
        binding_source='human_corrected', binding_validation={'valid': True, 'errors': []},
        finish_reason='confirmed_revision',
    )


def _atom_map(draft: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item['id']: item for item in draft['atomic_constraints']}


def _binding(draft: dict[str, Any], target: str) -> dict[str, Any]:
    if target == 'Applicability':
        return draft['applicability_binding']
    binding = next((item for item in draft['constraint_bindings'] if item['atomic_constraint_id'] == target), None)
    if binding is None:
        raise ValueError(f'Unknown binding target {target!r}.')
    return binding


def _replace_binding(draft: dict[str, Any], target: str, binding: dict[str, Any]) -> None:
    if target == 'Applicability':
        draft['applicability_binding'] = binding
        return
    for index, item in enumerate(draft['constraint_bindings']):
        if item['atomic_constraint_id'] == target:
            draft['constraint_bindings'][index] = binding
            return
    raise ValueError(f'Unknown binding target {target!r}.')


def _validate_binding_parameters(capability_id: str, parameters: Any,
                                 draft: dict[str, Any], target: str) -> None:
    atom = _atom_map(draft).get(target) or {}
    trace = ' '.join([
        draft['irr']['constraint_object'], draft['irr']['constraint_condition'],
        str(atom.get('normalized_constraint', '')),
    ])
    errors = _catalog_validate_parameters(capability_id, parameters, trace, prefix=target)
    if errors:
        raise ValueError('; '.join(errors))


def _build_binding(draft: dict[str, Any], target: str, capability_id: str,
                   parameters: dict[str, Any], paths: list[str] | None = None) -> dict[str, Any]:
    capability = CAPABILITY_CATALOG.get(capability_id)
    role = 'applicability' if target == 'Applicability' else 'constraint'
    if not capability or role not in capability.get('roles', []):
        raise ValueError(f'{capability_id!r} is not available for {target}.')
    _validate_binding_parameters(capability_id, parameters, draft, target)
    atom = _atom_map(draft).get(target)
    binding = materialize_binding(
        capability_id, parameters, role=role, atom=atom,
        object_text=draft['irr']['constraint_object'],
        compilation_strategy='human_corrected',
    )
    if paths is not None:
        _set_sources(binding, paths)
    return binding


def _operation_name(operation: dict[str, Any]) -> str:
    name = operation.get('operation') or operation.get('op')
    if name not in SUPPORTED_OPERATIONS:
        raise ValueError(f'Unsupported revision operation {name!r}.')
    return name


def apply_operations(draft: Any, operations: Any) -> dict[str, Any]:
    """Apply typed operations deterministically; the model never edits a draft directly."""
    result = deepcopy(draft)
    if not isinstance(operations, list) or not operations:
        raise ValueError('The model proposed no executable revision operations.')
    applied = []
    for index, operation in enumerate(operations, 1):
        if not isinstance(operation, dict):
            raise ValueError(f'Operation {index} is not an object.')
        name = _operation_name(operation)
        target = str(operation.get('target') or '')
        before = deepcopy(result)
        if name == 'set_logic':
            result['logic_tree'] = deepcopy(operation.get('logic_tree'))
        elif name in {'set_evidence_sources', 'replace_evidence_source', 'add_evidence_source', 'remove_evidence_source'}:
            binding = _binding(result, target)
            paths = [item['path'] for item in binding.get('evidence_sources', [])]
            if name == 'set_evidence_sources':
                paths = operation.get('paths')
            elif name == 'replace_evidence_source':
                old_path, new_path = operation.get('old_path'), operation.get('new_path')
                if old_path not in paths:
                    raise ValueError(f'{target} does not use {old_path!r}.')
                paths = [new_path if path == old_path else path for path in paths]
            elif name == 'add_evidence_source':
                paths.append(operation.get('path'))
            else:
                path = operation.get('path')
                if path not in paths:
                    raise ValueError(f'{target} does not use {path!r}.')
                paths = [item for item in paths if item != path]
            _set_sources(binding, paths)
        elif name == 'set_parameter':
            current = _binding(result, target)
            parameters = deepcopy(current.get('function_parameters') or {})
            parameter = operation.get('parameter')
            if not isinstance(parameter, str) or not parameter:
                raise ValueError('set_parameter requires a parameter name.')
            parameters[parameter] = deepcopy(operation.get('value'))
            paths = [item['path'] for item in current.get('evidence_sources', [])]
            replacement = _build_binding(result, target, current['capability_id'], parameters, paths)
            _replace_binding(result, target, replacement)
        elif name == 'set_capability':
            current = _binding(result, target)
            parameters = operation.get('parameters')
            if parameters is None:
                parameters = deepcopy(current.get('function_parameters') or {})
            replacement = _build_binding(
                result, target, operation.get('capability_id'), parameters,
                operation.get('paths'),
            )
            _replace_binding(result, target, replacement)
        elif name in {'add_atom', 'update_atom'}:
            atom = operation.get('atom')
            if not isinstance(atom, dict) or not atom.get('id') or not atom.get('normalized_constraint'):
                raise ValueError(f'{name} requires a complete atom.')
            atoms = _atom_map(result)
            exists = atom['id'] in atoms
            if name == 'add_atom' and exists:
                raise ValueError(f"Atomic ID {atom['id']} already exists.")
            if name == 'update_atom' and not exists:
                raise ValueError(f"Atomic ID {atom['id']} does not exist.")
            binding_spec = operation.get('binding')
            if not isinstance(binding_spec, dict):
                raise ValueError(f'{name} requires an explicit binding.')
            if exists:
                result['atomic_constraints'] = [deepcopy(atom) if item['id'] == atom['id'] else item for item in result['atomic_constraints']]
            else:
                result['atomic_constraints'].append(deepcopy(atom))
            binding = _build_binding(
                result, atom['id'], binding_spec.get('capability_id'),
                binding_spec.get('parameters') or {}, binding_spec.get('paths'),
            )
            if exists:
                _replace_binding(result, atom['id'], binding)
            else:
                result['constraint_bindings'].append(binding)
        elif name == 'remove_atom':
            if target not in _atom_map(result):
                raise ValueError(f'Atomic ID {target!r} does not exist.')
            result['atomic_constraints'] = [item for item in result['atomic_constraints'] if item['id'] != target]
            result['constraint_bindings'] = [item for item in result['constraint_bindings'] if item['atomic_constraint_id'] != target]
        if result == before:
            raise ValueError(f'Operation {index} ({name}) produced no change.')
        applied.append({'operation': name, 'target': target or 'DecisionLogic'})
    proposed = canonical_draft(result, result['irr'])
    if proposed == canonical_draft(draft, result['irr']):
        raise ValueError('The requested revision did not change the compilation draft.')
    proposed['_applied_operations'] = applied
    return proposed


def _expected_source(feedback: str) -> tuple[str, str] | None:
    """Recognize explicit field substitutions so an unrelated patch cannot pass."""
    lower = feedback.casefold()
    aliases = {
        'generic drug name': '用药信息.药品通用名',
        'medication name': '用药信息.药品名',
        'national medication code': '用药信息.药品国家编码',
        'icd-10 diagnosis name': '诊断.ICD10名称',
        'diagnosis name': '诊断.诊断名称',
        '药品通用名': '用药信息.药品通用名', '药品名': '用药信息.药品名',
        '药品国家编码': '用药信息.药品国家编码', 'icd10名称': '诊断.ICD10名称',
    }
    separators = [' instead of ', ' rather than ', '替代', '而不是']
    left = None
    for separator in separators:
        if separator in lower:
            left = lower.split(separator, 1)[0]
            break
    if left is None:
        return None
    matches = [(name, path) for name, path in aliases.items() if name.casefold() in left]
    if not matches:
        return None
    _, path = max(matches, key=lambda item: left.rfind(item[0].casefold()))
    target = 'Applicability' if 'applies when' in lower or 'applicability' in lower else ''
    return target, path


def _verify_feedback(feedback: str, proposed: dict[str, Any]) -> None:
    expected = _expected_source(feedback)
    if not expected:
        return
    target, path = expected
    bindings = [proposed['applicability_binding']] if target == 'Applicability' else [
        proposed['applicability_binding'], *proposed['constraint_bindings']]
    if not any(path in [item['path'] for item in binding.get('evidence_sources', [])] for binding in bindings):
        raise ValueError(f'The proposed revision did not apply the requested evidence source {path}.')


REVISION_INSTRUCTIONS = '''You translate human correction feedback into typed operations for a medical-insurance rule compiler.
Return one JSON object with keys summary and operations. Do not return a modified draft, Python, Markdown, or prose outside JSON.
Every operation must use one of these forms:
1. {"operation":"set_evidence_sources","target":"Applicability|A1|...","paths":["physical.path"]}
2. {"operation":"replace_evidence_source","target":"...","old_path":"...","new_path":"..."}
3. {"operation":"add_evidence_source|remove_evidence_source","target":"...","path":"..."}
4. {"operation":"set_parameter","target":"...","parameter":"name","value":<JSON value>}
5. {"operation":"set_capability","target":"...","capability_id":"registered id","parameters":{},"paths":[...]}
6. {"operation":"set_logic","target":"DecisionLogic","logic_tree":<complete and/or/not AST>}
7. {"operation":"add_atom|update_atom","target":"atomic id","atom":{"id":"...","normalized_constraint":"English","source_span":"exact policy span"},"binding":{"capability_id":"...","parameters":{},"paths":[...]}}
8. {"operation":"remove_atom","target":"atomic id"}. A separate set_logic operation must remove its AST reference.
Use target Applicability only for the independent object-matching check; never add it to the satisfaction AST.
Use only registered capabilities and their allowed_evidence_paths. Use only physical paths in the EMR schema.
Preserve unaffected atoms, logic, bindings and parameters by omitting operations for them.
When feedback says X instead of Y, emit replace_evidence_source with new_path X and old_path Y.
If the request cannot be represented, return {"summary":"...","operations":[],"error":"specific limitation"}.
Do not silently return an empty or unrelated operation list.'''


def _model_request(client: Any, model: str, payload: dict[str, Any], repair_error: str | None = None,
                   previous_output: str | None = None) -> tuple[dict[str, Any], str]:
    messages = [
        {'role': 'system', 'content': REVISION_INSTRUCTIONS},
        {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)},
    ]
    if repair_error is not None:
        messages.extend([
            {'role': 'assistant', 'content': previous_output or '{}'},
            {'role': 'user', 'content': 'The proposed operations failed deterministic validation: '
             + repair_error + '\nReturn a corrected JSON object that applies the original feedback.'},
        ])
    response = client.chat.completions.create(
        model=model, messages=messages, temperature=0,
        max_tokens=AgentAService._llm_config()['max_tokens'],
        response_format={'type': 'json_object'}, extra_body={'enable_thinking': False},
    )
    raw = response.choices[0].message.content or '{}'
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f'The model returned invalid JSON: {exc.msg}.') from exc
    return parsed, raw


def request_revision(raw: Any, irr: dict[str, str], feedback: Any) -> dict[str, Any]:
    if not isinstance(feedback, str) or not feedback.strip() or len(feedback) > 8000:
        raise ValueError('Enter revision feedback (up to 8,000 characters).')
    draft = canonical_draft(raw, irr)
    payload = {
        'policy': irr, 'current_draft': draft, 'feedback': feedback.strip(),
        'available_capabilities': public_catalog(list(CAPABILITY_CATALOG)),
        'emr_schema': _schema(), 'supported_operations': sorted(SUPPORTED_OPERATIONS),
    }
    client, model = AgentAService._create_client()
    previous_output = None
    validation_error = None
    try:
        for attempt in range(2):
            proposal, previous_output = _model_request(
                client, model, payload,
                repair_error=validation_error if attempt else None,
                previous_output=previous_output,
            )
            try:
                if not isinstance(proposal, dict):
                    raise ValueError('The model response must be a JSON object.')
                if proposal.get('error'):
                    raise ValueError(str(proposal['error']))
                proposed = apply_operations(draft, proposal.get('operations'))
                _verify_feedback(feedback, proposed)
                break
            except (ValueError, KeyError, TypeError) as exc:
                validation_error = str(exc)
                if attempt == 1:
                    raise ValueError(
                        'The requested revision could not be represented by the registered audit capabilities. '
                        + validation_error
                    ) from exc
        else:  # pragma: no cover
            raise ValueError('The revision could not be validated.')
    finally:
        client.close()
    applied = proposed.pop('_applied_operations', [])
    changes = []
    for key in ('atomic_constraints', 'logic_tree', 'applicability_binding', 'constraint_bindings'):
        if draft[key] != proposed[key]:
            changes.append({'section': key, 'before': draft[key], 'after': proposed[key]})
    if not changes:
        raise ValueError('The requested revision produced no visible change.')
    return {'draft': proposed, 'changes': changes, 'operations': applied,
            'summary': str(proposal.get('summary') or '') if isinstance(proposal, dict) else ''}
