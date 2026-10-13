import os
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from .models import Rule
from .serializers import RuleSerializer
from .services import AgentAService
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
            'A1 not satisfied: The patient has a diagnosis of duodenal ulcer.',
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
            'A1 must be absent but was present: A venous blood collection is charged at the same time.',
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
