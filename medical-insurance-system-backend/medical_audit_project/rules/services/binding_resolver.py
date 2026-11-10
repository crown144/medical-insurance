from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Callable

from .capability_catalog import CAPABILITY_CATALOG, get_capability


CATEGORY_STRATEGIES = {
    'Restricted Medication Use': {
        'name': 'restricted_medication_use',
        'object_kind': 'medication',
        'capability_ids': ['medication_name_matching'],
    },
    '超限定用药': {
        'name': 'restricted_medication_use',
        'object_kind': 'medication',
        'capability_ids': ['medication_name_matching'],
    },
    'Duplicate Charge': {
        'name': 'duplicate_charge',
        'object_kind': 'charge',
        'capability_ids': ['charge_record_filtering'],
    },
    '重复收费': {
        'name': 'duplicate_charge',
        'object_kind': 'charge',
        'capability_ids': ['charge_record_filtering'],
    },
    'Over-standard Charge': {
        'name': 'over_standard_charge',
        'object_kind': 'charge',
        'capability_ids': ['charge_record_filtering'],
    },
    '超标准收费': {
        'name': 'over_standard_charge',
        'object_kind': 'charge',
        'capability_ids': ['charge_record_filtering'],
    },
    'Excessive Frequency Billing': {
        'name': 'excessive_frequency_billing',
        'object_kind': 'charge',
        'capability_ids': ['charge_record_filtering'],
    },
    '超频次收费': {
        'name': 'excessive_frequency_billing',
        'object_kind': 'charge',
        'capability_ids': ['charge_record_filtering'],
    },
}


# Demo terminology and safe deterministic parameters. Executable metadata is
# defined only once, in CAPABILITY_CATALOG.
OBJECT_PROFILES = [
    {
        'kind': 'medication',
        'keywords': ('ilaprazole', '艾普拉唑'),
        'match_values': ['艾普拉唑', 'Ilaprazole'],
    },
    {
        'kind': 'medication',
        'keywords': ('calcium acetate', '醋酸钙'),
        'match_values': ['醋酸钙', 'Calcium acetate'],
    },
    {
        'kind': 'medication',
        'keywords': (
            'entecavir oral solution', 'entecavir',
            '恩替卡韦口服溶液', '恩替卡韦',
        ),
        'match_values': [
            '恩替卡韦口服溶液', '恩替卡韦',
            'Entecavir Oral Solution', 'Entecavir',
        ],
    },
    {
        'kind': 'charge',
        'keywords': ('intravenous injection', '静脉注射'),
        'match_values': ['静脉注射', 'Intravenous injection'],
    },
    {
        'kind': 'charge',
        'keywords': ('arterial pressure injection', '动脉加压注射'),
        'match_values': ['动脉加压注射', 'Arterial pressure injection'],
    },
]


CONSTRAINT_PROFILES = [
    {
        'capability_id': 'age_range',
        'keywords': (
            'aged 2 years to under 18 years',
            'aged 2 years to less than 18 years',
            'aged 2 to under 18',
            'aged 2 to less than 18',
            'between 2 and 18',
            '2 to under 18',
            '2 to less than 18',
            '2岁至<18岁',
            '2岁至小于18岁',
        ),
        'parameters': {
            'lower_operator': '>=', 'lower': 2,
            'upper_operator': '<', 'upper': 18,
        },
    },
    {
        'capability_id': 'age_comparison',
        'keywords': ('adult patient', 'is an adult', 'adult'),
        'parameters': {'operator': '>=', 'threshold': 18},
    },
    {
        'capability_id': 'diagnosis_name_matching',
        'keywords': (
            'chronic hepatitis b', 'chronic hbv infection',
            '慢性乙型肝炎', '慢性乙肝', '慢性hbv感染',
        ),
        'parameters': {
            'operator': 'contains',
            'match_values': [
                '慢性乙型肝炎', '慢性乙型病毒性肝炎', '慢性乙肝',
                'Chronic hepatitis B', 'Chronic HBV infection',
            ],
        },
    },
    {
        'capability_id': 'clinical_text_semantic_assessment',
        'keywords': ('compensated liver disease', 'compensated hepatic disease', '代偿性肝病'),
        'parameters': {
            'evidence_scope': 'clinical_narrative',
            'question': 'Does the record establish chronic HBV infection with compensated liver disease?',
        },
    },
    {
        'capability_id': 'clinical_text_semantic_assessment',
        'keywords': (
            'nucleoside-naive', 'nucleoside naive',
            'nucleoside treatment-naive', 'nucleoside-treatment-naive', '核苷初治',
        ),
        'parameters': {
            'evidence_scope': 'treatment_history',
            'question': 'Does the record establish that the patient is nucleoside-treatment-naive?',
        },
    },
    {
        'capability_id': 'diagnosis_name_matching',
        'keywords': ('duodenal ulcer', '十二指肠溃疡'),
        'parameters': {
            'operator': 'contains',
            'match_values': ['十二指肠溃疡', 'Duodenal ulcer'],
        },
    },
    {
        'capability_id': 'diagnosis_name_matching',
        'keywords': (
            'reflux esophagitis', 'gastroesophageal reflux',
            '反流性食管炎', '胃食管反流',
        ),
        'parameters': {
            'operator': 'contains',
            'match_values': ['反流性食管炎', '胃食管反流', 'Reflux esophagitis'],
        },
    },
    {
        'capability_id': 'diagnosis_name_matching',
        'keywords': ('hyperphosphatemia', '高磷血症'),
        'parameters': {
            'operator': 'contains',
            'match_values': ['高磷血症', 'Hyperphosphatemia'],
        },
    },
    {
        'capability_id': 'charge_record_filtering',
        'keywords': ('venous blood collection', '静脉采血'),
        'parameters': {
            'operator': 'contains',
            'match_values': ['静脉采血', 'Venous blood collection'],
            'relation': 'same_time_with_applicability',
        },
    },
    {
        'capability_id': 'charge_record_filtering',
        'keywords': ('arterial blood collection', '动脉采血'),
        'parameters': {
            'operator': 'contains',
            'match_values': ['动脉采血', 'Arterial blood collection'],
            'relation': 'same_time_with_applicability',
        },
    },
]


TRACEABLE_ALIAS_GROUPS = [
    ('艾普拉唑', 'Ilaprazole'),
    ('醋酸钙', 'Calcium acetate', 'Calcium acetate tablets'),
    ('恩替卡韦口服溶液', '恩替卡韦', 'Entecavir Oral Solution', 'Entecavir'),
    (
        '慢性乙型肝炎', '慢性乙型病毒性肝炎', '慢性乙肝', '慢性HBV感染',
        'chronic hepatitis b', 'chronic hbv infection',
    ),
    ('十二指肠溃疡', 'Duodenal ulcer'),
    ('反流性食管炎', '胃食管反流', 'Reflux esophagitis', 'Gastroesophageal reflux'),
    ('高磷血症', 'Hyperphosphatemia'),
    ('静脉注射', 'Intravenous injection'),
    ('静脉采血', 'Venous blood collection'),
    ('动脉加压注射', 'Arterial pressure injection'),
    ('动脉采血', 'Arterial blood collection'),
]


def resolve_bindings(
    irr: dict[str, str],
    atomic_constraints: list[dict[str, str]],
    logic_tree: dict[str, Any] | str,
    *,
    mode: str,
    fallback_enabled: bool,
    llm_request: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized_mode = (mode or 'hybrid').strip().lower()
    if normalized_mode not in {'llm', 'deterministic', 'hybrid'}:
        raise ValueError(f'Unsupported RULE_BINDING_MODE: {mode}')

    if normalized_mode == 'deterministic':
        return _deterministic_resolution(
            irr, atomic_constraints, source='deterministic',
        )

    try:
        if llm_request is None:
            raise RuntimeError('LLM binding request is unavailable.')
        raw_plan = llm_request()
        resolved = validate_and_materialize_binding_plan(
            raw_plan,
            irr,
            atomic_constraints,
            logic_tree,
        )
        if resolved['binding_validation']['valid']:
            resolved['binding_source'] = 'llm'
            _annotate_bindings(resolved, 'llm')
            return resolved
        failure_reason = '; '.join(resolved['binding_validation']['errors'])
    except Exception as exc:
        failure_reason = str(exc) or exc.__class__.__name__

    if normalized_mode == 'hybrid' or fallback_enabled:
        fallback = _deterministic_resolution(
            irr, atomic_constraints, source='deterministic_fallback',
        )
        fallback['binding_validation']['fallback_reason'] = failure_reason
        return fallback

    unbound = _unbound_resolution(irr, atomic_constraints, failure_reason)
    unbound['binding_source'] = 'llm'
    _annotate_bindings(unbound, 'llm')
    return unbound


def resolve_applicability_binding(irr: dict[str, str]) -> dict[str, Any]:
    category = irr.get('rule_category', '').strip()
    object_text = irr.get('constraint_object', '').strip()
    strategy = CATEGORY_STRATEGIES.get(category)
    profile = None
    if strategy:
        lowered = object_text.lower()
        profile = next(
            (
                item for item in OBJECT_PROFILES
                if item['kind'] == strategy['object_kind']
                and any(keyword.lower() in lowered for keyword in item['keywords'])
            ),
            None,
        )
    if not strategy or not profile:
        return _unbound_applicability(
            object_text,
            'No approved applicability capability matches the Constraint Object.',
            strategy['name'] if strategy else 'unsupported_rule_category',
        )

    capability_id = strategy['capability_ids'][0]
    parameters = {
        'operator': 'contains',
        'match_values': deepcopy(profile['match_values']),
    }
    if capability_id == 'charge_record_filtering':
        parameters['relation'] = 'exists'
    return materialize_binding(
        capability_id,
        parameters,
        role='applicability',
        object_text=object_text,
        compilation_strategy=strategy['name'],
    )


def resolve_constraint_bindings(
    atomic_constraints: list[dict[str, str]],
) -> list[dict[str, Any]]:
    bindings = []
    for atom in atomic_constraints:
        searchable = atom['normalized_constraint'].lower()
        profile = next(
            (
                item for item in CONSTRAINT_PROFILES
                if any(keyword.lower() in searchable for keyword in item['keywords'])
            ),
            None,
        )
        if profile is None:
            source_text = atom['source_span'].lower()
            source_matches = [
                item for item in CONSTRAINT_PROFILES
                if any(keyword.lower() in source_text for keyword in item['keywords'])
            ]
            if len(source_matches) == 1:
                profile = source_matches[0]
        if profile is None:
            bindings.append(_unbound_constraint(
                atom,
                'No approved EMR capability matches this constraint.',
            ))
            continue
        bindings.append(materialize_binding(
            profile['capability_id'],
            deepcopy(profile['parameters']),
            role='constraint',
            atom=atom,
        ))
    return bindings


def validate_and_materialize_binding_plan(
    plan: dict[str, Any],
    irr: dict[str, str],
    atomic_constraints: list[dict[str, str]],
    logic_tree: dict[str, Any] | str,
) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(plan, dict):
        raise ValueError('Binding LLM output must be a JSON object.')
    unknown_top_level = sorted(
        set(plan) - {'applicability_binding', 'constraint_bindings'}
    )
    if unknown_top_level:
        errors.append(
            f"Binding output contains unsupported fields: {', '.join(unknown_top_level)}."
        )

    app_plan = plan.get('applicability_binding')
    constraint_plans = plan.get('constraint_bindings')
    if not isinstance(app_plan, dict):
        app_plan = {}
        errors.append('Applicability: missing applicability_binding object.')
    if not isinstance(constraint_plans, list):
        constraint_plans = []
        errors.append('Constraint bindings must be an array.')

    allowed_app_fields = {
        'status', 'capability_id', 'parameters', 'source_reference', 'reason',
    }
    forbidden = sorted(set(app_plan) - allowed_app_fields)
    if forbidden:
        errors.append(
            f"Applicability: LLM output contains unsupported fields: {', '.join(forbidden)}."
        )

    app_binding = _validate_and_materialize_applicability(app_plan, irr, errors)
    atom_map = {atom['id']: atom for atom in atomic_constraints}
    plans_by_id: dict[str, list[dict[str, Any]]] = {}
    for index, item in enumerate(constraint_plans):
        if not isinstance(item, dict):
            errors.append(f'Constraint binding at index {index} must be an object.')
            continue
        atomic_id = str(item.get('atomic_id') or '').strip()
        plans_by_id.setdefault(atomic_id, []).append(item)

    bindings = []
    for atom in atomic_constraints:
        items = plans_by_id.get(atom['id'], [])
        if len(items) != 1:
            errors.append(
                f"{atom['id']}: expected exactly one binding, received {len(items)}."
            )
            bindings.append(_unbound_constraint(atom, 'Missing or duplicate LLM binding.'))
            continue
        bindings.append(_validate_and_materialize_constraint(items[0], atom, irr, errors))

    unknown_ids = sorted(set(plans_by_id) - set(atom_map))
    for atomic_id in unknown_ids:
        errors.append(f'{atomic_id or "<empty>"}: atomic_id is not defined by semantic decomposition.')

    referenced_ids = _logic_references(logic_tree)
    for atomic_id in referenced_ids:
        binding = next(
            (item for item in bindings if item['atomic_constraint_id'] == atomic_id),
            None,
        )
        if not binding or binding['status'] != 'bound':
            errors.append(f'{atomic_id}: logic tree atom is not successfully bound.')

    if app_binding['status'] != 'bound':
        errors.append('Applicability: binding is not successfully bound.')

    errors = list(dict.fromkeys(errors))
    return {
        'applicability_binding': app_binding,
        'constraint_bindings': bindings,
        'binding_source': 'llm',
        'binding_validation': {'valid': not errors, 'errors': errors},
    }


def materialize_binding(
    capability_id: str,
    parameters: dict[str, Any],
    *,
    role: str,
    atom: dict[str, str] | None = None,
    object_text: str = '',
    compilation_strategy: str = '',
) -> dict[str, Any]:
    capability = get_capability(capability_id)
    if capability is None:
        raise ValueError(f'Unknown capability_id {capability_id}.')

    parameters = deepcopy(parameters)
    if 'match_values' in parameters:
        parameters['match_values'] = _expand_approved_aliases(
            parameters['match_values']
        )
    runtime = deepcopy(capability['runtime'])
    function_parameters = deepcopy(parameters)
    if capability_id in {'medication_name_matching', 'diagnosis_name_matching'}:
        runtime['match_values'] = deepcopy(parameters['match_values'])
    elif capability_id == 'charge_record_filtering':
        runtime['match_values'] = deepcopy(parameters['match_values'])
        relation = parameters.get('relation', 'exists')
        runtime['relation'] = (
            'same_time_with_applicability'
            if relation == 'same_time_with_applicability'
            else None
        )
        if runtime['relation'] is None:
            runtime.pop('time_field', None)
    elif capability_id in {'age_comparison', 'numeric_comparison'}:
        runtime['comparisons'] = [
            (parameters['operator'], parameters['threshold']),
        ]
    elif capability_id == 'age_range':
        runtime['comparisons'] = [
            (parameters['lower_operator'], parameters['lower']),
            (parameters['upper_operator'], parameters['upper']),
        ]
    elif capability_id in {
        'statistical_calculation', 'temporal_interval_calculation',
    }:
        runtime.update({
            'method': parameters['method'],
            'operator': parameters['operator'],
            'threshold': parameters['threshold'],
        })
    elif capability_id == 'list_membership':
        runtime['expected_values'] = deepcopy(parameters['expected_values'])
    elif capability_id == 'clinical_text_semantic_assessment':
        runtime['question'] = parameters['question']

    materialized_field = capability['field']
    materialized_field_key = capability['field_key']
    variants = capability.get('materialization_variants', {})
    if variants:
        variant = variants[parameters['evidence_scope']]
        materialized_field = variant['field']
        materialized_field_key = variant['field_key']

    common = {
        'binding_type': role,
        'capability_id': capability_id,
        'status': 'bound',
        'validation_status': 'valid',
        'data_source': capability['data_source'],
        'field': materialized_field,
        'field_key': materialized_field_key,
        'audit_function': capability['function'],
        'function_parameters': function_parameters,
        'expected_condition': True if role == 'applicability' else atom['normalized_constraint'],
        'runtime': runtime,
    }
    if role == 'applicability':
        common.update({
            'object': object_text,
            'compilation_strategy': compilation_strategy,
        })
    else:
        common.update({
            'atomic_constraint_id': atom['id'],
            'normalized_constraint': atom['normalized_constraint'],
        })
    return common


def _validate_and_materialize_applicability(
    plan: dict[str, Any],
    irr: dict[str, str],
    errors: list[str],
) -> dict[str, Any]:
    object_text = irr.get('constraint_object', '').strip()
    strategy = CATEGORY_STRATEGIES.get(irr.get('rule_category', '').strip())
    if plan.get('status') != 'bound':
        reason = str(plan.get('reason') or 'No approved applicability capability was selected.')
        errors.append(f'Applicability: {reason}')
        return _unbound_applicability(
            object_text,
            reason,
            strategy['name'] if strategy else 'unsupported_rule_category',
        )

    capability_id = str(plan.get('capability_id') or '').strip()
    if not strategy or capability_id not in strategy['capability_ids']:
        errors.append(
            f'Applicability: capability_id {capability_id or "<empty>"} is not approved for this rule category.'
        )
        return _unbound_applicability(
            object_text,
            'Invalid applicability capability.',
            strategy['name'] if strategy else 'unsupported_rule_category',
        )
    reference = plan.get('source_reference') or {}
    if (
        reference.get('type') != 'constraint_object'
        or str(reference.get('text') or '').strip().lower() != object_text.lower()
    ):
        errors.append('Applicability: source_reference must exactly reference Constraint Object.')

    parameters = plan.get('parameters')
    parameter_errors = _validate_parameters(
        capability_id,
        parameters,
        object_text,
        prefix='Applicability',
    )
    errors.extend(parameter_errors)
    if parameter_errors:
        return _unbound_applicability(
            object_text,
            'Invalid applicability parameters.',
            strategy['name'],
        )
    return materialize_binding(
        capability_id,
        parameters,
        role='applicability',
        object_text=object_text,
        compilation_strategy=strategy['name'],
    )


def _validate_and_materialize_constraint(
    plan: dict[str, Any],
    atom: dict[str, str],
    irr: dict[str, str],
    errors: list[str],
) -> dict[str, Any]:
    allowed_fields = {
        'atomic_id', 'status', 'capability_id', 'parameters', 'source_span', 'reason',
    }
    forbidden = sorted(set(plan) - allowed_fields)
    if forbidden:
        errors.append(
            f"{atom['id']}: LLM output contains unsupported fields: {', '.join(forbidden)}."
        )
    if plan.get('status') != 'bound':
        reason = str(plan.get('reason') or 'No approved capability can evaluate this condition.')
        errors.append(f"{atom['id']}: {reason}")
        return _unbound_constraint(atom, reason)

    capability_id = str(plan.get('capability_id') or '').strip()
    capability = CAPABILITY_CATALOG.get(capability_id)
    if not capability or 'constraint' not in capability.get('roles', []):
        errors.append(
            f"{atom['id']}: capability_id {capability_id or '<empty>'} is not an approved constraint capability."
        )
        return _unbound_constraint(atom, 'Invalid capability_id.')

    supplied_span = str(plan.get('source_span') or '').strip()
    if supplied_span != atom['source_span']:
        errors.append(f"{atom['id']}: source_span was modified by the binding model.")

    trace_text = ' '.join([
        atom['normalized_constraint'],
        atom['source_span'],
        irr.get('constraint_object', ''),
    ])
    parameters = plan.get('parameters')
    parameter_errors = _validate_parameters(
        capability_id,
        parameters,
        trace_text,
        prefix=atom['id'],
    )
    errors.extend(parameter_errors)
    if parameter_errors or forbidden:
        return _unbound_constraint(atom, 'Binding validation failed.')
    return materialize_binding(
        capability_id,
        parameters,
        role='constraint',
        atom=atom,
    )


def _validate_parameters(
    capability_id: str,
    parameters: Any,
    trace_text: str,
    *,
    prefix: str,
) -> list[str]:
    capability = CAPABILITY_CATALOG.get(capability_id)
    if capability is None:
        return [f'{prefix}: unknown capability_id {capability_id}.']
    if not isinstance(parameters, dict):
        return [f'{prefix}: parameters must be an object.']

    errors = []
    schema = capability['parameter_schema']
    unknown = sorted(set(parameters) - set(schema))
    if unknown:
        errors.append(f'{prefix}: unsupported parameters: {", ".join(unknown)}.')
    for name in capability.get('required_parameters', []):
        if name not in parameters:
            errors.append(f'{prefix}: missing required parameter {name}.')
    for name, value in parameters.items():
        spec = schema.get(name)
        if not spec:
            continue
        expected_type = spec.get('type')
        if expected_type == 'string' and not isinstance(value, str):
            errors.append(f'{prefix}: parameter {name} must be a string.')
            continue
        if expected_type == 'number' and (
            isinstance(value, bool) or not isinstance(value, (int, float))
        ):
            errors.append(f'{prefix}: parameter {name} must be a number.')
            continue
        if expected_type == 'array':
            if not isinstance(value, list):
                errors.append(f'{prefix}: parameter {name} must be an array.')
                continue
            if len(value) < spec.get('minItems', 0):
                errors.append(f'{prefix}: parameter {name} contains too few values.')
            if spec.get('items', {}).get('type') == 'string' and not all(
                isinstance(item, str) and item.strip() for item in value
            ):
                errors.append(f'{prefix}: parameter {name} must contain non-empty strings.')
        if 'enum' in spec and value not in spec['enum']:
            errors.append(f'{prefix}: parameter {name} has unsupported value {value!r}.')
        if isinstance(value, str) and len(value) < spec.get('minLength', 0):
            errors.append(f'{prefix}: parameter {name} is too short.')

    if errors:
        return errors
    return _validate_parameter_traceability(
        capability_id,
        parameters,
        trace_text,
        prefix,
    )


def _validate_parameter_traceability(
    capability_id: str,
    parameters: dict[str, Any],
    trace_text: str,
    prefix: str,
) -> list[str]:
    errors = []
    lowered = trace_text.lower()
    numbers = {
        float(value) for value in re.findall(r'(?<![a-z])\d+(?:\.\d+)?', lowered)
    }
    numeric_values = []
    if 'threshold' in parameters:
        numeric_values.append(parameters['threshold'])
    numeric_values.extend(
        parameters[name] for name in ('lower', 'upper') if name in parameters
    )
    for value in numeric_values:
        if float(value) not in numbers and not (
            capability_id == 'age_comparison'
            and float(value) == 18
            and 'adult' in lowered
        ):
            errors.append(f'{prefix}: numeric value {value} is not traceable to the rule text.')

    if capability_id in {
        'age_comparison', 'age_range', 'numeric_comparison',
        'statistical_calculation', 'temporal_interval_calculation',
    }:
        operator_items = [
            (name, parameters[name])
            for name in ('operator', 'lower_operator', 'upper_operator')
            if name in parameters
        ]
        for name, operator in operator_items:
            if not _operator_is_traceable(operator, lowered, name):
                errors.append(
                    f'{prefix}: {name} value {operator!r} is not traceable to the rule text.'
                )

    for key in ('match_values', 'expected_values'):
        for value in parameters.get(key, []):
            if not _value_is_traceable(str(value), lowered):
                errors.append(
                    f'{prefix}: {key} value {value!r} is not traceable to the rule text or approved aliases.'
                )

    relation = parameters.get('relation')
    if relation == 'same_time_with_applicability' and not any(
        marker in lowered for marker in ('same time', 'simultaneous', '同时', '同一秒', '同日')
    ):
        errors.append(f'{prefix}: same-time relation is not traceable to the rule text.')

    if capability_id == 'clinical_text_semantic_assessment':
        scope = parameters['evidence_scope']
        if scope == 'treatment_history' and not any(
            marker in lowered
            for marker in ('treatment', 'therapy', 'naive', 'history', '初治', '治疗', '病史')
        ):
            errors.append(f'{prefix}: treatment_history scope is not traceable to the atomic constraint.')
        question_words = {
            word for word in re.findall(r'[a-z]{4,}', parameters['question'].lower())
            if word not in {'does', 'record', 'patient', 'establish', 'medical'}
        }
        source_words = set(re.findall(r'[a-z]{4,}', lowered))
        if not question_words.intersection(source_words):
            errors.append(f'{prefix}: semantic question is not traceable to the atomic constraint.')
    return errors


def _value_is_traceable(value: str, lowered_source: str) -> bool:
    lowered_value = value.strip().lower()
    if lowered_value and lowered_value in lowered_source:
        return True
    for aliases in TRACEABLE_ALIAS_GROUPS:
        lowered_aliases = {item.lower() for item in aliases}
        if lowered_value in lowered_aliases and any(
            alias in lowered_source for alias in lowered_aliases
        ):
            return True
    return False


def _operator_is_traceable(operator: str, text: str, parameter_name: str) -> bool:
    markers = {
        '>': ('greater than', 'more than', 'exceeds', '超过', '>'),
        '>=': ('at least', 'or older', 'minimum', 'adult', '不少于', '不低于', '>='),
        '<': ('under', 'younger than', 'less than', 'below', '未满', '小于', '<'),
        '<=': ('at most', 'no more than', 'maximum', '不超过', '不高于', '<='),
        '==': ('equal to', 'exactly', '等于', '为', '=='),
    }
    if any(marker in text for marker in markers.get(operator, ())):
        return True
    if parameter_name == 'lower_operator' and operator == '>=':
        return bool(re.search(r'\b\d+(?:\.\d+)?\s+(?:to|through)\b', text))
    return False


def _expand_approved_aliases(values: list[str]) -> list[str]:
    expanded = list(values)
    lowered_values = {value.strip().lower() for value in values}
    for aliases in TRACEABLE_ALIAS_GROUPS:
        lowered_aliases = {item.lower() for item in aliases}
        if lowered_values.intersection(lowered_aliases):
            expanded.extend(aliases)
    return list(dict.fromkeys(expanded))


def _logic_references(node: Any) -> set[str]:
    if isinstance(node, str):
        return {node}
    references: set[str] = set()
    if isinstance(node, dict):
        for operands in node.values():
            if isinstance(operands, list):
                for operand in operands:
                    references.update(_logic_references(operand))
    return references


def _deterministic_resolution(
    irr: dict[str, str],
    atoms: list[dict[str, str]],
    *,
    source: str,
) -> dict[str, Any]:
    applicability = resolve_applicability_binding(irr)
    constraints = resolve_constraint_bindings(atoms)
    errors = []
    if applicability['status'] != 'bound':
        errors.append('Applicability: Constraint Object has no approved applicability binding.')
    errors.extend(
        f"{item['atomic_constraint_id']}: {item['expected_condition']}"
        for item in constraints
        if item['status'] != 'bound'
    )
    result = {
        'applicability_binding': applicability,
        'constraint_bindings': constraints,
        'binding_source': source,
        'binding_validation': {'valid': not errors, 'errors': errors},
    }
    _annotate_bindings(result, source)
    return result


def _unbound_resolution(
    irr: dict[str, str],
    atoms: list[dict[str, str]],
    reason: str,
) -> dict[str, Any]:
    return {
        'applicability_binding': _unbound_applicability(
            irr.get('constraint_object', ''), reason, 'unresolved',
        ),
        'constraint_bindings': [
            _unbound_constraint(atom, reason) for atom in atoms
        ],
        'binding_source': 'llm',
        'binding_validation': {'valid': False, 'errors': [reason]},
    }


def _unbound_applicability(
    object_text: str,
    reason: str,
    strategy: str,
) -> dict[str, Any]:
    return {
        'binding_type': 'applicability',
        'object': object_text,
        'capability_id': None,
        'status': 'unbound',
        'validation_status': 'invalid',
        'compilation_strategy': strategy,
        'data_source': 'Unbound',
        'field': 'Unbound',
        'field_key': 'unbound',
        'audit_function': 'Unbound',
        'function_parameters': {},
        'expected_condition': reason,
    }


def _unbound_constraint(atom: dict[str, str], reason: str) -> dict[str, Any]:
    return {
        'binding_type': 'constraint',
        'atomic_constraint_id': atom['id'],
        'normalized_constraint': atom['normalized_constraint'],
        'capability_id': None,
        'status': 'unbound',
        'validation_status': 'invalid',
        'data_source': 'Unbound',
        'field': 'Unbound',
        'field_key': 'unbound',
        'audit_function': 'Unbound',
        'function_parameters': {},
        'expected_condition': reason,
    }


def _annotate_bindings(result: dict[str, Any], source: str) -> None:
    result['applicability_binding']['binding_source'] = source
    for binding in result['constraint_bindings']:
        binding['binding_source'] = source
