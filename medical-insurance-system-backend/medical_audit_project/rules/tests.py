import os
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from engine.over_standard_v2 import (
    calc_date_interval_stats,
    calc_numeric_stats,
    calc_stats,
)

from .models import Rule
from .serializers import RuleSerializer
from .services import AgentAService
from .services.binding_resolver import (
    resolve_bindings,
    resolve_constraint_bindings,
    validate_and_materialize_binding_plan,
)
from .services.deterministic_compiler import compile_rule
from .services.semantic_decomposer import (
    expand_supported_compound_atoms,
    ground_source_spans,
    validate_decomposition,
)


class RuleSerializerTests(TestCase):
    def test_partial_status_update_does_not_replace_rule_fields(self):
        rule = Rule(
            rule_id='R-STATUS-TEST',
            drug_name='Status test rule',
            description='Status update test',
            rule_code='def execute_rule(ctx):\n    return submit_result(False)',
            status=False,
        )

        serializer = RuleSerializer(
            rule,
            data={'enabled': True},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data, {'status': True})


class CatalogConstrainedBindingTests(SimpleTestCase):
    irr = {
        'rule_category': 'Restricted Medication Use',
        'constraint_object': 'Entecavir Oral Solution',
        'constraint_condition': 'Policy condition',
    }

    @staticmethod
    def applicability_plan():
        return {
            'status': 'bound',
            'capability_id': 'medication_name_matching',
            'parameters': {
                'operator': 'contains',
                'match_values': ['Entecavir Oral Solution'],
            },
            'source_reference': {
                'type': 'constraint_object',
                'text': 'Entecavir Oral Solution',
            },
        }

    def resolve_atom(self, atom, binding):
        plan = {
            'applicability_binding': self.applicability_plan(),
            'constraint_bindings': [{
                'atomic_id': atom['id'],
                'source_span': atom['source_span'],
                **binding,
            }],
        }
        return validate_and_materialize_binding_plan(
            plan,
            self.irr,
            [atom],
            atom['id'],
        )

    def test_adult_age_materializes_age_comparison(self):
        atom = {
            'id': 'A1',
            'normalized_constraint': 'The patient is an adult.',
            'source_span': 'adult patients',
        }
        result = self.resolve_atom(atom, {
            'status': 'bound',
            'capability_id': 'age_comparison',
            'parameters': {'operator': '>=', 'threshold': 18},
        })

        binding = result['constraint_bindings'][0]
        self.assertTrue(result['binding_validation']['valid'])
        self.assertEqual(binding['capability_id'], 'age_comparison')
        self.assertEqual(binding['audit_function'], 'is_compare')
        self.assertEqual(binding['runtime']['comparisons'], [('>=', 18)])

    def test_pediatric_range_materializes_age_range(self):
        atom = {
            'id': 'A1',
            'normalized_constraint': 'The patient is aged 2 to under 18 years.',
            'source_span': 'aged 2 to under 18 years',
        }
        result = self.resolve_atom(atom, {
            'status': 'bound',
            'capability_id': 'age_range',
            'parameters': {
                'lower_operator': '>=', 'lower': 2,
                'upper_operator': '<', 'upper': 18,
            },
        })

        binding = result['constraint_bindings'][0]
        self.assertTrue(result['binding_validation']['valid'])
        self.assertEqual(binding['runtime']['comparisons'], [('>=', 2), ('<', 18)])

    def test_pediatric_range_is_supported_by_deterministic_fallback(self):
        atom = {
            'id': 'A3',
            'normalized_constraint': (
                'The patient is a child aged 2 years to under 18 years.'
            ),
            'source_span': '2岁至<18岁',
        }

        binding = resolve_constraint_bindings([atom])[0]

        self.assertEqual(binding['status'], 'bound')
        self.assertEqual(binding['capability_id'], 'age_range')
        self.assertEqual(binding['data_source'], 'Insurance Information')
        self.assertEqual(binding['field'], 'Age')
        self.assertEqual(binding['audit_function'], 'is_compare')
        self.assertEqual(binding['function_parameters'], {
            'lower_operator': '>=',
            'lower': 2,
            'upper_operator': '<',
            'upper': 18,
        })

    def test_numeric_statistics_materialize_and_compile_to_numeric_function(self):
        atom = {
            'id': 'A1',
            'normalized_constraint': 'The total charge amount exceeds 100.',
            'source_span': 'The total charge amount exceeds 100.',
        }
        result = self.resolve_atom(atom, {
            'status': 'bound',
            'capability_id': 'statistical_calculation',
            'parameters': {
                'method': 'sum', 'operator': '>', 'threshold': 100,
            },
        })

        binding = result['constraint_bindings'][0]
        self.assertTrue(result['binding_validation']['valid'])
        self.assertEqual(binding['audit_function'], 'calc_numeric_stats')
        code = compile_rule('A1', result['applicability_binding'], [binding])
        self.assertIn("calc_numeric_stats(a1_values, 'sum')", code)
        self.assertNotIn('calc_stats(a1_values', code)

    def test_date_intervals_materialize_and_compile_to_date_function(self):
        atom = {
            'id': 'A1',
            'normalized_constraint': (
                'The minimum interval between charges is less than 7 days.'
            ),
            'source_span': (
                'The minimum interval between charges is less than 7 days.'
            ),
        }
        result = self.resolve_atom(atom, {
            'status': 'bound',
            'capability_id': 'temporal_interval_calculation',
            'parameters': {
                'method': 'min_gap', 'operator': '<', 'threshold': 7,
            },
        })

        binding = result['constraint_bindings'][0]
        self.assertTrue(result['binding_validation']['valid'])
        self.assertEqual(binding['data_source'], 'Charge Records')
        self.assertEqual(binding['field'], 'Charge Date')
        self.assertEqual(binding['audit_function'], 'calc_date_interval_stats')
        code = compile_rule('A1', result['applicability_binding'], [binding])
        self.assertIn("calc_date_interval_stats(a1_values, 'min_gap')", code)

    def test_split_statistical_functions_and_legacy_dispatcher(self):
        values = [10, 20, 30]
        dates = ['2026-01-01', '2026-01-04', '2026-01-10']

        self.assertEqual(calc_numeric_stats(values, 'count'), 3)
        self.assertEqual(calc_numeric_stats(values, 'sum'), 60)
        self.assertEqual(calc_numeric_stats(values, 'avg'), 20)
        self.assertEqual(calc_date_interval_stats(dates, 'span_days'), 9)
        self.assertEqual(calc_date_interval_stats(dates, 'min_gap'), 3)
        self.assertEqual(calc_date_interval_stats(dates, 'max_gap'), 6)
        self.assertEqual(calc_stats(values, 'sum'), 60)
        self.assertEqual(calc_stats(dates, 'span_days'), 9)

    def test_chronic_hepatitis_materializes_diagnosis_matching(self):
        atom = {
            'id': 'A1',
            'normalized_constraint': 'The patient has chronic hepatitis B.',
            'source_span': 'chronic hepatitis B',
        }
        result = self.resolve_atom(atom, {
            'status': 'bound',
            'capability_id': 'diagnosis_name_matching',
            'parameters': {
                'operator': 'contains',
                'match_values': ['Chronic hepatitis B'],
            },
        })

        binding = result['constraint_bindings'][0]
        self.assertTrue(result['binding_validation']['valid'])
        self.assertEqual(binding['data_source'], 'Diagnosis Records')
        self.assertEqual(binding['field'], 'Diagnosis Name')
        self.assertEqual(binding['audit_function'], 'filter_list')

    def test_nucleoside_naive_materializes_runtime_llm_bool(self):
        atom = {
            'id': 'A1',
            'normalized_constraint': 'The patient is nucleoside-treatment-naive.',
            'source_span': 'nucleoside-naive patient',
        }
        result = self.resolve_atom(atom, {
            'status': 'bound',
            'capability_id': 'clinical_text_semantic_assessment',
            'parameters': {
                'evidence_scope': 'treatment_history',
                'question': 'Is the patient documented as nucleoside-treatment-naive?',
            },
        })

        binding = result['constraint_bindings'][0]
        self.assertTrue(result['binding_validation']['valid'])
        self.assertEqual(binding['data_source'], 'Admission Record')
        self.assertEqual(binding['field'], 'Treatment History')
        self.assertEqual(binding['audit_function'], 'llm_bool')

    def test_unbound_condition_fails_validation(self):
        atom = {
            'id': 'A1',
            'normalized_constraint': 'The patient has an unsupported genomic marker.',
            'source_span': 'unsupported genomic marker',
        }
        result = self.resolve_atom(atom, {
            'status': 'unbound',
            'reason': 'No approved capability can evaluate this condition.',
        })

        self.assertFalse(result['binding_validation']['valid'])
        self.assertEqual(result['constraint_bindings'][0]['status'], 'unbound')
        self.assertTrue(any('A1' in error for error in result['binding_validation']['errors']))

    def test_unknown_capability_id_fails_validation(self):
        atom = {
            'id': 'A1',
            'normalized_constraint': 'The patient is an adult.',
            'source_span': 'adult patients',
        }
        result = self.resolve_atom(atom, {
            'status': 'bound',
            'capability_id': 'invented_capability',
            'parameters': {},
        })

        self.assertFalse(result['binding_validation']['valid'])
        self.assertTrue(any('invented_capability' in error for error in result['binding_validation']['errors']))

    def test_invalid_parameters_fail_validation(self):
        atom = {
            'id': 'A1',
            'normalized_constraint': 'The patient is at least 18 years old.',
            'source_span': 'at least 18 years old',
        }
        result = self.resolve_atom(atom, {
            'status': 'bound',
            'capability_id': 'age_comparison',
            'parameters': {'operator': 'approximately', 'threshold': 'eighteen'},
        })

        self.assertFalse(result['binding_validation']['valid'])
        self.assertTrue(any('operator' in error for error in result['binding_validation']['errors']))
        self.assertTrue(any('threshold' in error for error in result['binding_validation']['errors']))

    def test_entecavir_applicability_uses_medication_capability(self):
        atom = {
            'id': 'A1',
            'normalized_constraint': 'The patient is an adult.',
            'source_span': 'adult patients',
        }
        result = self.resolve_atom(atom, {
            'status': 'bound',
            'capability_id': 'age_comparison',
            'parameters': {'operator': '>=', 'threshold': 18},
        })

        binding = result['applicability_binding']
        self.assertTrue(result['binding_validation']['valid'])
        self.assertEqual(binding['capability_id'], 'medication_name_matching')
        self.assertEqual(binding['data_source'], 'Medication Records')
        self.assertEqual(binding['field'], 'Generic Drug Name')

    def test_hybrid_mode_reports_deterministic_fallback(self):
        atom = {
            'id': 'A1',
            'normalized_constraint': 'The patient is an adult.',
            'source_span': 'adult patients',
        }
        result = resolve_bindings(
            self.irr,
            [atom],
            'A1',
            mode='hybrid',
            fallback_enabled=True,
            llm_request=lambda: {'invalid': 'output'},
        )

        self.assertTrue(result['binding_validation']['valid'])
        self.assertEqual(result['binding_source'], 'deterministic_fallback')
        self.assertIn('fallback_reason', result['binding_validation'])

    @mock.patch('rules.services.agenta_service.compile_rule')
    @mock.patch('rules.services.agenta_service.resolve_bindings')
    @mock.patch('rules.services.agenta_service.AgentAService._create_client')
    def test_invalid_binding_stops_python_generation(
        self,
        mock_create_client,
        mock_resolve_bindings,
        mock_compile_rule,
    ):
        semantic_response = SimpleNamespace(
            choices=[SimpleNamespace(
                finish_reason='stop',
                message=SimpleNamespace(content='''{
                    "atomic_constraints": [{
                        "id": "A1",
                        "normalized_constraint": "The patient has an unsupported genomic marker.",
                        "source_span": "unsupported genomic marker"
                    }],
                    "logic_tree": "A1"
                }'''),
            )],
        )
        client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=mock.Mock(return_value=semantic_response)),
            ),
        )
        mock_create_client.return_value = (client, 'test-model')
        mock_resolve_bindings.return_value = {
            'applicability_binding': {
                'status': 'bound',
                'validation_status': 'valid',
                'audit_function': 'filter_list',
            },
            'constraint_bindings': [{
                'atomic_constraint_id': 'A1',
                'status': 'unbound',
                'validation_status': 'invalid',
            }],
            'binding_source': 'llm',
            'binding_validation': {
                'valid': False,
                'errors': ['A1: No approved capability can evaluate this condition.'],
            },
        }

        result = AgentAService.build(irr={
            'rule_category': 'Restricted Medication Use',
            'constraint_object': 'Entecavir Oral Solution',
            'constraint_condition': 'unsupported genomic marker',
        })

        self.assertEqual(result.generated_code, '')
        self.assertFalse(result.validation['valid'])
        mock_compile_rule.assert_not_called()

    @mock.patch('rules.services.agenta_service.AgentAService._create_client')
    def test_valid_llm_binding_path_is_reported(self, mock_create_client):
        semantic_response = SimpleNamespace(
            choices=[SimpleNamespace(
                finish_reason='stop',
                message=SimpleNamespace(content='''{
                    "atomic_constraints": [{
                        "id": "A1",
                        "normalized_constraint": "The patient is an adult.",
                        "source_span": "adult patients"
                    }],
                    "logic_tree": "A1"
                }'''),
            )],
        )
        binding_response = SimpleNamespace(
            choices=[SimpleNamespace(
                finish_reason='stop',
                message=SimpleNamespace(content='''{
                    "applicability_binding": {
                        "status": "bound",
                        "capability_id": "medication_name_matching",
                        "parameters": {
                            "operator": "contains",
                            "match_values": ["Entecavir Oral Solution"]
                        },
                        "source_reference": {
                            "type": "constraint_object",
                            "text": "Entecavir Oral Solution"
                        }
                    },
                    "constraint_bindings": [{
                        "atomic_id": "A1",
                        "status": "bound",
                        "capability_id": "age_comparison",
                        "parameters": {"operator": ">=", "threshold": 18},
                        "source_span": "adult patients"
                    }]
                }'''),
            )],
        )
        client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=mock.Mock(side_effect=[semantic_response, binding_response]),
                ),
            ),
        )
        mock_create_client.return_value = (client, 'test-model')

        result = AgentAService.build(irr={
            'rule_category': 'Restricted Medication Use',
            'constraint_object': 'Entecavir Oral Solution',
            'constraint_condition': 'adult patients',
        })

        self.assertEqual(result.binding_source, 'llm')
        self.assertTrue(result.binding_validation['valid'])
        self.assertEqual(
            result.constraint_bindings[0]['capability_id'],
            'age_comparison',
        )
        self.assertIn('condition_satisfied = A1', result.generated_code)


class AgentAViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @mock.patch('rules.views.AgentAService.build')
    def test_generate_returns_json_timeout_error(self, mock_build):
        mock_build.side_effect = TimeoutError('request timed out')

        response = self.client.post(
            '/api/rules/agenta/generate/',
            {'rule_text': '规则名称：测试\n规则描述：测试规则'},
            format='json',
        )

        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.data['code'], 1)
        self.assertIn('timed out', response.data['message'])
        self.assertEqual(response.data['result']['error_type'], 'TimeoutError')

    @mock.patch('rules.views.AgentAService.build')
    def test_generate_returns_json_model_error(self, mock_build):
        mock_build.side_effect = RuntimeError('model unavailable')

        response = self.client.post(
            '/api/rules/agenta/generate/',
            {'rule_text': '规则名称：测试\n规则描述：测试规则'},
            format='json',
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data['code'], 1)
        self.assertEqual(response.data['message'], 'Rule compilation failed.')
        self.assertEqual(response.data['result']['error_type'], 'RuntimeError')


class DeterministicCompilationTests(TestCase):
    @mock.patch('rules.services.agenta_service.AgentAService._create_client')
    def test_supported_rule_falls_back_when_llm_normalized_text_contains_chinese(
        self,
        mock_create_client,
    ):
        response = SimpleNamespace(
            choices=[SimpleNamespace(
                finish_reason='stop',
                message=SimpleNamespace(content='''{
                    "atomic_constraints": [{
                        "id": "A1",
                        "normalized_constraint": "Venous blood collection 静脉采血 is charged at the same time.",
                        "source_span": "静脉采血"
                    }],
                    "logic_tree": {"not": ["A1"]}
                }'''),
            )],
        )
        client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=mock.Mock(return_value=response)),
            ),
        )
        mock_create_client.return_value = (client, 'test-model')

        result = AgentAService.build(irr={
            'rule_category': 'Duplicate Charge',
            'constraint_object': 'Intravenous injection',
            'constraint_condition': (
                'Intravenous injection and venous blood collection cannot be charged together.'
            ),
        })

        self.assertEqual(result.rule_snapshot['runtime_mode'], 'validated_semantic_fallback')
        self.assertEqual(result.logical_expression, 'NOT A1')
        self.assertEqual(
            result.atomic_constraints[0]['normalized_constraint'],
            'A venous blood collection is charged at the same time.',
        )
        self.assertTrue(result.validation['valid'])

    def test_compound_entecavir_atoms_are_split_before_binding(self):
        decomposition = validate_decomposition({
            'atomic_constraints': [
                {
                    'id': 'A1',
                    'normalized_constraint': 'Patient is an adult with chronic hepatitis B',
                    'source_span': '慢性乙型肝炎成人患者',
                },
                {
                    'id': 'A2',
                    'normalized_constraint': 'Patient is a child aged 2 years to less than 18 years',
                    'source_span': '2岁至<18岁',
                },
                {
                    'id': 'A3',
                    'normalized_constraint': 'Patient has chronic HBV infection with compensated liver disease',
                    'source_span': '慢性HBV感染代偿性肝病',
                },
                {
                    'id': 'A4',
                    'normalized_constraint': 'Patient is nucleoside-treatment-naive',
                    'source_span': '核苷初治',
                },
            ],
            'logic_tree': {
                'or': [
                    {'and': ['A1']},
                    {'and': ['A2', 'A3', 'A4']},
                ],
            },
        })

        expanded = expand_supported_compound_atoms(decomposition)

        self.assertEqual(len(expanded['atomic_constraints']), 6)
        self.assertEqual(
            expanded['logic_tree'],
            {
                'or': [
                    {'and': ['A1', 'A2']},
                    {'and': ['A3', 'A4', 'A5', 'A6']},
                ],
            },
        )

    def test_non_exact_source_span_falls_back_to_rule_condition(self):
        condition = '使用艾普拉唑须有十二指肠溃疡或反流性食管炎诊断'
        atoms = ground_source_spans(
            [{
                'id': 'A1',
                'normalized_constraint': 'The patient has a qualifying diagnosis.',
                'source_span': 'A translated model span',
            }],
            condition,
        )

        self.assertEqual(atoms[0]['source_span'], condition)

    def test_logic_tree_normalizes_structured_atom_references(self):
        result = validate_decomposition({
            'atomic_constraints': [
                {
                    'id': 'A1',
                    'normalized_constraint': 'The target item is present.',
                    'source_span': '目标项目存在',
                },
                {
                    'id': 'A2',
                    'normalized_constraint': 'The required diagnosis is present.',
                    'source_span': '存在所需诊断',
                },
            ],
            'logic_tree': {
                'AND': [
                    {'id': 'A1'},
                    {'ref': 'A2'},
                ],
            },
        })

        self.assertEqual(result['logic_tree'], {'and': ['A1', 'A2']})

    @mock.patch.dict(os.environ, {'AGENTA_DISABLE_LLM_TEST': '1'})
    def test_existing_rule_fields_build_irr_and_deterministic_program(self):
        irr = {
            'rule_category': 'Restricted Medication Use',
            'constraint_object': 'Ilaprazole',
            'constraint_condition': 'Ilaprazole requires a duodenal ulcer or reflux esophagitis diagnosis.',
        }

        first = AgentAService.build(irr=irr)
        second = AgentAService.build(irr=irr)

        self.assertEqual(first.irr, irr)
        self.assertEqual(first.logical_expression, 'A1 OR A2')
        self.assertEqual(first.applicability_binding['object'], 'Ilaprazole')
        self.assertEqual(first.applicability_binding['field_key'], 'medication_name')
        self.assertEqual(len(first.constraint_bindings), 2)
        self.assertTrue(all(item['status'] == 'bound' for item in first.execution_bindings))
        self.assertIn('is_applicable = len(applicability_matches) > 0', first.generated_code)
        self.assertIn('condition_satisfied = (A1 or A2)', first.generated_code)
        self.assertIn(
            'A1 not satisfied: The patient has a diagnosis of duodenal ulcer',
            first.generated_code,
        )
        self.assertNotIn('The rule conditions are not satisfied.', first.generated_code)
        self.assertNotIn('is_applicable = A1', first.generated_code)
        self.assertEqual(first.generated_code, second.generated_code)
        self.assertTrue(first.validation['valid'])

    @mock.patch.dict(os.environ, {'AGENTA_DISABLE_LLM_TEST': '1'})
    def test_duplicate_charge_uses_constraint_object_for_applicability(self):
        result = AgentAService.build(irr={
            'rule_category': 'Duplicate Charge',
            'constraint_object': 'Intravenous injection',
            'constraint_condition': (
                'Intravenous injection and venous blood collection cannot be charged together.'
            ),
        })

        self.assertEqual(result.logical_expression, 'NOT A1')
        self.assertEqual(result.applicability_binding['field_key'], 'charge_item_name')
        self.assertEqual(len(result.constraint_bindings), 1)
        self.assertIn('is_applicable = len(applicability_matches) > 0', result.generated_code)
        self.assertNotIn('is_applicable = A1', result.generated_code)
        self.assertIn(
            'A1 must be absent but was present: A venous blood collection is charged at the same time',
            result.generated_code,
        )

    @mock.patch.dict(os.environ, {'AGENTA_DISABLE_LLM_TEST': '1'})
    def test_entecavir_rule_uses_approved_structured_and_text_bindings(self):
        result = AgentAService.build(irr={
            'rule_category': '超限定用药',
            'constraint_object': '恩替卡韦口服溶液',
            'constraint_condition': (
                '限慢性乙型肝炎成人患者或2岁至<18岁慢性HBV感染代偿性肝病的'
                '核苷初治儿童患者。'
            ),
        })

        self.assertEqual(
            result.logical_expression,
            '(A1 AND A2) OR (A3 AND A4 AND A5 AND A6)',
        )
        self.assertEqual(result.applicability_binding['status'], 'bound')
        self.assertEqual(result.applicability_binding['field_key'], 'medication_name')
        self.assertTrue(all(item['status'] == 'bound' for item in result.constraint_bindings))
        self.assertIn('恩替卡韦口服溶液', result.generated_code)
        self.assertIn('is_compare(value', result.generated_code)
        self.assertIn('llm_bool(', result.generated_code)
        self.assertIn(
            'condition_satisfied = ((A1 and A2) or (A3 and A4 and A5 and A6))',
            result.generated_code,
        )
        self.assertTrue(result.validation['valid'])

    def test_validation_rejects_imports_and_unknown_calls(self):
        result = AgentAService.validate_code(
            'import os\n\ndef execute_rule(ctx):\n    unknown_call()\n    return submit_result(True)'
        )

        self.assertFalse(result['valid'])
        self.assertIn('imports are not allowed', result['errors'])
        self.assertTrue(any('unknown_call' in error for error in result['errors']))
