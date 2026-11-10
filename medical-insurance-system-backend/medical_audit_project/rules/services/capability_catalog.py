from __future__ import annotations

from copy import deepcopy
from typing import Any


COMPARISON_OPERATORS = ['>', '>=', '<', '<=', '==']


# This is the single authoritative definition of executable rule capabilities.
# Public fields may be sent to the binding LLM; runtime fields never leave the
# backend and are attached only after deterministic validation.
CAPABILITY_CATALOG: dict[str, dict[str, Any]] = {
    'medication_name_matching': {
        'capability_id': 'medication_name_matching',
        'description': 'Match an audited medication by generic medication name.',
        'roles': ['applicability'],
        'object_kinds': ['medication'],
        'data_source': 'Medication Records',
        'field': 'Generic Drug Name',
        'field_key': 'medication_name',
        'function': 'filter_list',
        'parameter_schema': {
            'operator': {'type': 'string', 'enum': ['contains']},
            'match_values': {
                'type': 'array', 'items': {'type': 'string'}, 'minItems': 1,
            },
        },
        'required_parameters': ['operator', 'match_values'],
        'supported_examples': [
            'The patient used Ilaprazole.',
            'The patient used Entecavir Oral Solution.',
        ],
        'runtime': {
            'mode': 'list_filter',
            'source_path': '用药信息',
            'field_path': '药品通用名',
        },
    },
    'diagnosis_name_matching': {
        'capability_id': 'diagnosis_name_matching',
        'description': 'Match a diagnosis using approved diagnosis-name aliases.',
        'roles': ['constraint'],
        'data_source': 'Diagnosis Records',
        'field': 'Diagnosis Name',
        'field_key': 'diagnosis_name',
        'function': 'filter_list',
        'parameter_schema': {
            'operator': {'type': 'string', 'enum': ['contains']},
            'match_values': {
                'type': 'array', 'items': {'type': 'string'}, 'minItems': 1,
            },
        },
        'required_parameters': ['operator', 'match_values'],
        'supported_examples': [
            'The patient has chronic hepatitis B.',
            'The patient has a diagnosis of duodenal ulcer.',
        ],
        'runtime': {
            'mode': 'list_filter',
            'source_paths': ['诊断信息', '诊断'],
            'field_path': '诊断名称',
        },
    },
    'age_comparison': {
        'capability_id': 'age_comparison',
        'description': 'Compare patient age with a policy-defined threshold.',
        'roles': ['constraint'],
        'data_source': 'Insurance Information',
        'field': 'Age',
        'field_key': 'patient_age',
        'function': 'is_compare',
        'parameter_schema': {
            'operator': {'type': 'string', 'enum': COMPARISON_OPERATORS},
            'threshold': {'type': 'number'},
        },
        'required_parameters': ['operator', 'threshold'],
        'supported_examples': ['The patient is at least 18 years old.'],
        'runtime': {
            'mode': 'numeric_comparison',
            'source_path': '医保信息',
            'field_path': '年龄',
        },
    },
    'age_range': {
        'capability_id': 'age_range',
        'description': 'Check whether patient age is within a policy-defined range.',
        'roles': ['constraint'],
        'data_source': 'Insurance Information',
        'field': 'Age',
        'field_key': 'patient_age',
        'function': 'is_compare',
        'parameter_schema': {
            'lower_operator': {'type': 'string', 'enum': ['>', '>=']},
            'lower': {'type': 'number'},
            'upper_operator': {'type': 'string', 'enum': ['<', '<=']},
            'upper': {'type': 'number'},
        },
        'required_parameters': [
            'lower_operator', 'lower', 'upper_operator', 'upper',
        ],
        'supported_examples': ['The patient is aged 2 to under 18 years.'],
        'runtime': {
            'mode': 'numeric_comparison',
            'source_path': '医保信息',
            'field_path': '年龄',
        },
    },
    'charge_record_filtering': {
        'capability_id': 'charge_record_filtering',
        'description': 'Match a charge item and optionally relate it to the audited charge time.',
        'roles': ['applicability', 'constraint'],
        'object_kinds': ['charge'],
        'data_source': 'Charge Records',
        'field': 'Charge Item Name',
        'field_key': 'charge_item_name',
        'function': 'filter_list',
        'parameter_schema': {
            'operator': {'type': 'string', 'enum': ['contains']},
            'match_values': {
                'type': 'array', 'items': {'type': 'string'}, 'minItems': 1,
            },
            'relation': {
                'type': 'string',
                'enum': ['exists', 'same_time_with_applicability'],
            },
        },
        'required_parameters': ['operator', 'match_values'],
        'supported_examples': [
            'A venous blood collection is charged at the same time.',
            'The audited charge item exists.',
        ],
        'runtime': {
            'mode': 'list_filter',
            'source_path': '收费报告',
            'field_path': '收费项目名称',
            'time_field': '收费日期',
        },
    },
    'numeric_comparison': {
        'capability_id': 'numeric_comparison',
        'description': 'Compare a charge amount with a policy-defined numeric threshold.',
        'roles': ['constraint'],
        'data_source': 'Charge Records',
        'field': 'Charge Amount',
        'field_key': 'charge_amount',
        'function': 'is_compare',
        'parameter_schema': {
            'operator': {'type': 'string', 'enum': COMPARISON_OPERATORS},
            'threshold': {'type': 'number'},
        },
        'required_parameters': ['operator', 'threshold'],
        'supported_examples': ['The charge amount is greater than 100.'],
        'runtime': {
            'mode': 'numeric_comparison',
            'source_path': '收费报告',
            'field_path': '金额',
        },
    },
    'statistical_calculation': {
        'capability_id': 'statistical_calculation',
        'description': 'Calculate a statistic over charge amounts and compare the result.',
        'roles': ['constraint'],
        'data_source': 'Charge Records',
        'field': 'Charge Amount',
        'field_key': 'charge_amount',
        'function': 'calc_numeric_stats',
        'parameter_schema': {
            'method': {
                'type': 'string',
                'enum': ['sum', 'count', 'avg', 'max', 'min', 'distinct_count'],
            },
            'operator': {'type': 'string', 'enum': COMPARISON_OPERATORS},
            'threshold': {'type': 'number'},
        },
        'required_parameters': ['method', 'operator', 'threshold'],
        'supported_examples': ['The total charge amount exceeds 100.'],
        'runtime': {
            'mode': 'numeric_statistical_comparison',
            'source_path': '收费报告',
            'field_path': '金额',
        },
    },
    'temporal_interval_calculation': {
        'capability_id': 'temporal_interval_calculation',
        'description': 'Calculate the span or adjacent gaps between charge dates and compare the result.',
        'roles': ['constraint'],
        'data_source': 'Charge Records',
        'field': 'Charge Date',
        'field_key': 'charge_date',
        'function': 'calc_date_interval_stats',
        'parameter_schema': {
            'method': {
                'type': 'string',
                'enum': ['span_days', 'min_gap', 'max_gap'],
            },
            'operator': {'type': 'string', 'enum': COMPARISON_OPERATORS},
            'threshold': {'type': 'number'},
        },
        'required_parameters': ['method', 'operator', 'threshold'],
        'supported_examples': [
            'The minimum interval between charges is less than 7 days.',
        ],
        'runtime': {
            'mode': 'temporal_interval_comparison',
            'source_path': '收费报告',
            'field_path': '收费日期',
        },
    },
    'list_membership': {
        'capability_id': 'list_membership',
        'description': 'Check whether a structured list contains an approved policy value.',
        'roles': ['constraint'],
        'data_source': 'Diagnosis Records',
        'field': 'Diagnosis Code',
        'field_key': 'diagnosis_code',
        'function': 'list_contains',
        'parameter_schema': {
            'expected_values': {
                'type': 'array', 'items': {'type': 'string'}, 'minItems': 1,
            },
        },
        'required_parameters': ['expected_values'],
        'supported_examples': ['The diagnosis-code list contains K21.'],
        'runtime': {
            'mode': 'list_membership',
            'source_path': '诊断信息',
            'field_path': 'ICD编码',
        },
    },
    'clinical_text_semantic_assessment': {
        'capability_id': 'clinical_text_semantic_assessment',
        'description': 'Assess a policy condition using approved admission-record text.',
        'roles': ['constraint'],
        'data_source': 'Admission Record',
        'field': 'Clinical Narrative',
        'field_key': 'admission_clinical_text',
        'function': 'llm_bool',
        'parameter_schema': {
            'evidence_scope': {
                'type': 'string',
                'enum': ['clinical_narrative', 'treatment_history'],
            },
            'question': {'type': 'string', 'minLength': 10},
        },
        'required_parameters': ['evidence_scope', 'question'],
        'supported_examples': [
            'The patient has compensated liver disease.',
            'The patient is nucleoside-treatment-naive.',
        ],
        'runtime': {
            'mode': 'llm_bool',
            'context_paths': [
                '入院记录.现病史',
                '入院记录.既往史',
                '入院记录.初步诊断',
                '入院记录.更正诊断',
            ],
        },
        'materialization_variants': {
            'clinical_narrative': {
                'field': 'Clinical Narrative',
                'field_key': 'admission_clinical_text',
            },
            'treatment_history': {
                'field': 'Treatment History',
                'field_key': 'treatment_history',
            },
        },
    },
}


def get_capability(capability_id: str) -> dict[str, Any] | None:
    capability = CAPABILITY_CATALOG.get(capability_id)
    return deepcopy(capability) if capability else None


def public_capability(capability_id: str) -> dict[str, Any]:
    capability = CAPABILITY_CATALOG[capability_id]
    return {
        key: deepcopy(value)
        for key, value in capability.items()
        if key not in {
            'runtime', 'field_key', 'object_kinds', 'materialization_variants',
        }
    }


def public_catalog(capability_ids: list[str]) -> list[dict[str, Any]]:
    return [public_capability(item) for item in capability_ids]

