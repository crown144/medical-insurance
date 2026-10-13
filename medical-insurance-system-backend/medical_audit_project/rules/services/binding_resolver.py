from __future__ import annotations

from typing import Any


CATEGORY_STRATEGIES = {
    'Restricted Medication Use': {
        'name': 'restricted_medication_use',
        'object_kind': 'medication',
    },
    '超限定用药': {
        'name': 'restricted_medication_use',
        'object_kind': 'medication',
    },
    'Duplicate Charge': {
        'name': 'duplicate_charge',
        'object_kind': 'charge',
    },
    '重复收费': {
        'name': 'duplicate_charge',
        'object_kind': 'charge',
    },
    'Over-standard Charge': {
        'name': 'over_standard_charge',
        'object_kind': 'charge',
    },
    '超标准收费': {
        'name': 'over_standard_charge',
        'object_kind': 'charge',
    },
    'Excessive Frequency Billing': {
        'name': 'excessive_frequency_billing',
        'object_kind': 'charge',
    },
    '超频次收费': {
        'name': 'excessive_frequency_billing',
        'object_kind': 'charge',
    },
}


CAPABILITIES = [
    {
        'kind': 'medication',
        'keywords': ('ilaprazole', '艾普拉唑'),
        'data_source': 'Medication Records',
        'field': 'Generic Drug Name',
        'field_key': 'medication_name',
        'match_values': ['艾普拉唑', 'Ilaprazole'],
        'runtime': {'source_path': '用药信息', 'field_path': '药品通用名'},
    },
    {
        'kind': 'medication',
        'keywords': ('calcium acetate', '醋酸钙'),
        'data_source': 'Medication Records',
        'field': 'Generic Drug Name',
        'field_key': 'medication_name',
        'match_values': ['醋酸钙', 'Calcium acetate'],
        'runtime': {'source_path': '用药信息', 'field_path': '药品通用名'},
    },
    {
        'kind': 'medication',
        'keywords': ('entecavir oral solution', 'entecavir', '恩替卡韦口服溶液', '恩替卡韦'),
        'data_source': 'Medication Records',
        'field': 'Generic Drug Name',
        'field_key': 'medication_name',
        'match_values': ['恩替卡韦口服溶液', '恩替卡韦', 'Entecavir oral solution', 'Entecavir'],
        'runtime': {'source_path': '用药信息', 'field_path': '药品通用名'},
    },
    {
        'kind': 'age',
        'capability_id': 'pediatric_age_range',
        'keywords': ('aged 2 to under 18', 'between 2 and 18', '2 to under 18'),
        'data_source': 'Insurance Information',
        'field': 'Age',
        'field_key': 'patient_age',
        'audit_function': 'is_compare',
        'function_parameters': {
            'comparisons': [
                {'operator': '>=', 'threshold': 2},
                {'operator': '<', 'threshold': 18},
            ],
        },
        'expected_condition': 'Age is at least 2 and under 18 years.',
        'runtime': {
            'mode': 'numeric_comparison',
            'source_path': '医保信息',
            'field_path': '年龄',
            'comparisons': [('>=', 2), ('<', 18)],
        },
    },
    {
        'kind': 'age',
        'capability_id': 'minimum_age_2',
        'keywords': ('at least 2 years', '2 years or older', 'aged 2 or older'),
        'data_source': 'Insurance Information',
        'field': 'Age',
        'field_key': 'patient_age',
        'audit_function': 'is_compare',
        'function_parameters': {'operator': '>=', 'threshold': 2},
        'expected_condition': 'Age is at least 2 years.',
        'runtime': {
            'mode': 'numeric_comparison',
            'source_path': '医保信息',
            'field_path': '年龄',
            'comparisons': [('>=', 2)],
        },
    },
    {
        'kind': 'age',
        'capability_id': 'maximum_age_18',
        'keywords': ('under 18', 'younger than 18', 'less than 18'),
        'data_source': 'Insurance Information',
        'field': 'Age',
        'field_key': 'patient_age',
        'audit_function': 'is_compare',
        'function_parameters': {'operator': '<', 'threshold': 18},
        'expected_condition': 'Age is under 18 years.',
        'runtime': {
            'mode': 'numeric_comparison',
            'source_path': '医保信息',
            'field_path': '年龄',
            'comparisons': [('<', 18)],
        },
    },
    {
        'kind': 'age',
        'capability_id': 'adult_age',
        'keywords': ('adult patient', 'is an adult', 'adult'),
        'data_source': 'Insurance Information',
        'field': 'Age',
        'field_key': 'patient_age',
        'audit_function': 'is_compare',
        'function_parameters': {'operator': '>=', 'threshold': 18},
        'expected_condition': 'Age is at least 18 years.',
        'runtime': {
            'mode': 'numeric_comparison',
            'source_path': '医保信息',
            'field_path': '年龄',
            'comparisons': [('>=', 18)],
        },
    },
    {
        'kind': 'diagnosis',
        'keywords': (
            'chronic hepatitis b', 'chronic hbv infection',
            '慢性乙型肝炎', '慢性乙肝', '慢性hbv感染',
        ),
        'data_source': 'Diagnosis Records',
        'field': 'Diagnosis Name',
        'field_key': 'diagnosis_name',
        'match_values': [
            '慢性乙型肝炎', '慢性乙型病毒性肝炎', '慢性乙肝',
            'chronic hepatitis B', 'chronic HBV infection',
        ],
        'runtime': {
            'source_paths': ['诊断信息', '诊断'],
            'field_path': '诊断名称',
        },
    },
    {
        'kind': 'clinical_text',
        'capability_id': 'compensated_liver_disease',
        'keywords': ('compensated liver disease', 'compensated hepatic disease', '代偿性肝病'),
        'data_source': 'Admission Record',
        'field': 'Clinical Narrative',
        'field_key': 'admission_clinical_text',
        'audit_function': 'llm_bool',
        'function_parameters': {
            'question': 'Does the record establish chronic HBV infection with compensated liver disease?',
        },
        'expected_condition': 'Chronic HBV infection with compensated liver disease is documented.',
        'runtime': {
            'mode': 'llm_bool',
            'context_paths': [
                '入院记录.现病史', '入院记录.既往史',
                '入院记录.初步诊断', '入院记录.更正诊断',
            ],
            'question': 'Does the record establish chronic HBV infection with compensated liver disease?',
        },
    },
    {
        'kind': 'clinical_text',
        'capability_id': 'nucleoside_naive',
        'keywords': (
            'nucleoside-naive', 'nucleoside naive', 'nucleoside treatment-naive',
            'nucleoside-treatment-naive', '核苷初治',
        ),
        'data_source': 'Admission Record',
        'field': 'Treatment History',
        'field_key': 'treatment_history',
        'audit_function': 'llm_bool',
        'function_parameters': {
            'question': 'Does the record establish that the pediatric patient is nucleoside-treatment-naive?',
        },
        'expected_condition': 'The pediatric patient is documented as nucleoside-treatment-naive.',
        'runtime': {
            'mode': 'llm_bool',
            'context_paths': [
                '入院记录.现病史', '入院记录.既往史',
                '入院记录.初步诊断', '入院记录.更正诊断',
            ],
            'question': 'Does the record establish that the pediatric patient is nucleoside-treatment-naive?',
        },
    },
    {
        'kind': 'diagnosis',
        'keywords': ('duodenal ulcer', '十二指肠溃疡'),
        'data_source': 'Diagnosis Records',
        'field': 'Diagnosis Name',
        'field_key': 'diagnosis_name',
        'match_values': ['十二指肠溃疡', 'duodenal ulcer'],
        'runtime': {'source_path': '诊断信息', 'field_path': '诊断名称'},
    },
    {
        'kind': 'diagnosis',
        'keywords': ('reflux esophagitis', 'gastroesophageal reflux', '反流性食管炎', '胃食管反流'),
        'data_source': 'Diagnosis Records',
        'field': 'Diagnosis Name',
        'field_key': 'diagnosis_name',
        'match_values': ['反流性食管炎', '胃食管反流', 'reflux esophagitis'],
        'runtime': {'source_path': '诊断信息', 'field_path': '诊断名称'},
    },
    {
        'kind': 'diagnosis',
        'keywords': ('hyperphosphatemia', '高磷血症'),
        'data_source': 'Diagnosis Records',
        'field': 'Diagnosis Name',
        'field_key': 'diagnosis_name',
        'match_values': ['高磷血症', 'hyperphosphatemia'],
        'runtime': {'source_path': '诊断信息', 'field_path': '诊断名称'},
    },
    {
        'kind': 'charge',
        'keywords': ('intravenous injection', '静脉注射'),
        'data_source': 'Charge Records',
        'field': 'Charge Item Name',
        'field_key': 'charge_item_name',
        'match_values': ['静脉注射', 'intravenous injection'],
        'runtime': {'source_path': '收费报告', 'field_path': '收费项目名称'},
    },
    {
        'kind': 'charge',
        'keywords': ('venous blood collection', '静脉采血'),
        'data_source': 'Charge Records',
        'field': 'Charge Item Name',
        'field_key': 'charge_item_name',
        'match_values': ['静脉采血', 'venous blood collection'],
        'runtime': {'source_path': '收费报告', 'field_path': '收费项目名称'},
        'relation': 'same_time_with_applicability',
    },
    {
        'kind': 'charge',
        'keywords': ('arterial pressure injection', '动脉加压注射'),
        'data_source': 'Charge Records',
        'field': 'Charge Item Name',
        'field_key': 'charge_item_name',
        'match_values': ['动脉加压注射', 'arterial pressure injection'],
        'runtime': {'source_path': '收费报告', 'field_path': '收费项目名称'},
    },
    {
        'kind': 'charge',
        'keywords': ('arterial blood collection', '动脉采血'),
        'data_source': 'Charge Records',
        'field': 'Charge Item Name',
        'field_key': 'charge_item_name',
        'match_values': ['动脉采血', 'arterial blood collection'],
        'runtime': {'source_path': '收费报告', 'field_path': '收费项目名称'},
        'relation': 'same_time_with_applicability',
    },
]


def resolve_applicability_binding(irr: dict[str, str]) -> dict[str, Any]:
    category = irr.get('rule_category', '').strip()
    object_text = irr.get('constraint_object', '').strip()
    strategy = CATEGORY_STRATEGIES.get(category)
    capability = None
    if strategy:
        lowered = object_text.lower()
        capability = next(
            (
                item for item in CAPABILITIES
                if item['kind'] == strategy['object_kind']
                and any(keyword.lower() in lowered for keyword in item['keywords'])
            ),
            None,
        )

    if capability is None:
        return {
            'binding_type': 'applicability',
            'object': object_text,
            'status': 'unbound',
            'compilation_strategy': strategy['name'] if strategy else 'unsupported_rule_category',
            'data_source': 'Unbound',
            'field': 'Unbound',
            'field_key': 'unbound',
            'audit_function': 'Unbound',
            'function_parameters': {},
            'expected_condition': 'No approved applicability capability matches the Constraint Object.',
        }

    return {
        'binding_type': 'applicability',
        'object': object_text,
        'status': 'bound',
        'compilation_strategy': strategy['name'],
        'data_source': capability['data_source'],
        'field': capability['field'],
        'field_key': capability['field_key'],
        'audit_function': 'filter_list',
        'function_parameters': {
            'operator': 'contains',
            'match_value': _english_match_value(capability),
        },
        'expected_condition': True,
        'runtime': {
            **capability['runtime'],
            'match_values': capability['match_values'],
        },
    }


def resolve_constraint_bindings(
    atomic_constraints: list[dict[str, str]],
) -> list[dict[str, Any]]:
    bindings = []
    for atom in atomic_constraints:
        searchable = atom['normalized_constraint'].lower()
        capability = next(
            (
                item for item in CAPABILITIES
                if _capability_matches(item, searchable)
            ),
            None,
        )
        if capability is None:
            source_text = atom['source_span'].lower()
            source_matches = [
                item for item in CAPABILITIES
                if _capability_matches(item, source_text)
            ]
            if len(source_matches) == 1:
                capability = source_matches[0]
        if capability is None:
            bindings.append({
                'binding_type': 'constraint',
                'atomic_constraint_id': atom['id'],
                'normalized_constraint': atom['normalized_constraint'],
                'status': 'unbound',
                'data_source': 'Unbound',
                'field': 'Unbound',
                'field_key': 'unbound',
                'audit_function': 'Unbound',
                'function_parameters': {},
                'expected_condition': 'No approved EMR capability matches this constraint.',
            })
            continue

        relation = capability.get('relation')
        audit_function = capability.get('audit_function', 'filter_list')
        parameters = capability.get('function_parameters') or {
            'operator': 'contains',
            'match_value': _english_match_value(capability),
        }
        expected_condition: bool | str = capability.get('expected_condition', True)
        if relation == 'same_time_with_applicability':
            parameters['time_field'] = 'Charge Date'
            parameters['same_time_with'] = 'Constraint Object'
            expected_condition = 'A matching charge exists at the same time as the audited object.'
        runtime = {
            **capability['runtime'],
            'relation': relation,
            'time_field': '收费日期' if relation == 'same_time_with_applicability' else None,
        }
        if 'match_values' in capability:
            runtime['match_values'] = capability['match_values']

        bindings.append({
            'binding_type': 'constraint',
            'atomic_constraint_id': atom['id'],
            'normalized_constraint': atom['normalized_constraint'],
            'status': 'bound',
            'data_source': capability['data_source'],
            'field': capability['field'],
            'field_key': capability['field_key'],
            'audit_function': audit_function,
            'function_parameters': parameters,
            'expected_condition': expected_condition,
            'runtime': runtime,
        })
    return bindings


def _capability_matches(capability: dict[str, Any], text: str) -> bool:
    capability_id = capability.get('capability_id')
    if capability_id == 'pediatric_age_range':
        return (
            any(token in text for token in ('age', 'aged', 'year', 'between', 'younger'))
            and '2' in text
            and '18' in text
        )
    if capability_id == 'adult_age':
        return (
            any(keyword.lower() in text for keyword in capability['keywords'])
            or ('18' in text and any(token in text for token in ('at least', 'or older', 'minimum age')))
        )
    if capability_id == 'compensated_liver_disease':
        return (
            any(keyword.lower() in text for keyword in capability['keywords'])
            or ('compensated' in text and ('liver' in text or 'hepatic' in text))
        )
    if capability_id == 'nucleoside_naive':
        return (
            any(keyword.lower() in text for keyword in capability['keywords'])
            or ('nucleoside' in text and 'naive' in text)
        )
    return any(keyword.lower() in text for keyword in capability['keywords'])


def _english_match_value(capability: dict[str, Any]) -> str:
    return next(value for value in capability['match_values'] if value.isascii())
