import json
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock, patch

from rules import test_compiled_runtime as fixtures
from rules.services import revision_service as service
from rules.services.readable_renderer import compiled_plan_from_code
from engine.compiled_runtime import execute_compiled_plan


class RevisionTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.CompiledRuntimeTests()
        fixture.setUp()
        self.case = fixture.case
        self.irr = {
            'rule_category': '超限定用药',
            'constraint_object': 'Drug X',
            'constraint_condition': 'Condition X or condition Y must be documented.',
        }
        self.draft = {
            'irr': self.irr,
            'atomic_constraints': [
                {'id': 'A1', 'normalized_constraint': 'Condition X is documented.', 'source_span': 'Condition X'},
                {'id': 'A2', 'normalized_constraint': 'Condition Y is established.', 'source_span': 'condition Y'},
            ],
            'logic_tree': {'or': ['A1', 'A2']},
            'applicability_binding': fixture.app,
            'constraint_bindings': [fixture.atom, fixture.text],
        }

    def apply(self, *operations):
        result = service.apply_operations(self.draft, list(operations))
        result.pop('_applied_operations', None)
        return result

    def test_typed_logic_revision_preserves_bindings_and_changes_runtime(self):
        revised = self.apply({'operation': 'set_logic', 'target': 'DecisionLogic',
                              'logic_tree': {'and': ['A1', 'A2']}})
        self.assertEqual(revised['constraint_bindings'], self.draft['constraint_bindings'])
        old_plan = compiled_plan_from_code(service.compile_draft(self.draft, self.irr).generated_code)
        new_plan = compiled_plan_from_code(service.compile_draft(revised, self.irr).generated_code)
        self.assertEqual(old_plan['logic'], {'or': ['A1', 'A2']})
        self.assertEqual(new_plan['logic'], {'and': ['A1', 'A2']})
        stub = {'value': False, 'insufficient_evidence': False, 'evidence': [], 'reason': 'Negative.'}
        with patch.object(fixtures.compiled_runtime, 'llm_evidence', return_value=stub) as llm:
            self.assertEqual(execute_compiled_plan(self.case, new_plan)['review_status'], 'violation')
            llm.assert_called_once()

    def test_applicability_source_replacement_changes_real_plan(self):
        old_path = '用药信息.药品通用名'
        new_path = '用药信息.药品名'
        revised = self.apply({'operation': 'replace_evidence_source', 'target': 'Applicability',
                              'old_path': old_path, 'new_path': new_path})
        plan = compiled_plan_from_code(service.compile_draft(revised, self.irr).generated_code)
        self.assertEqual(plan['applicability']['evidence_sources'][0]['path'], new_path)
        self.assertEqual(plan['applicability']['field'], 'Medication Name')
        self.assertEqual(plan['applicability']['runtime']['field_path'], '药品名')
        case = {'用药信息': [{'药品名': 'Drug X'}], '诊断': [{'诊断名称': 'Condition X'}]}
        self.assertEqual(execute_compiled_plan(case, plan)['review_status'], 'compliant')

    def test_multisource_text_binding_can_be_changed(self):
        revised = self.apply({'operation': 'set_evidence_sources', 'target': 'A2', 'paths': [
            '入院记录.现病史', '入院记录.既往史', '首次病程记录.诊断依据',
        ]})
        binding = revised['constraint_bindings'][1]
        self.assertEqual(binding['source_count'], 3)
        self.assertEqual(binding['runtime']['context_paths'], [
            '入院记录.现病史', '入院记录.既往史', '首次病程记录.诊断依据',
        ])

    def test_incompatible_or_unknown_source_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'cannot use'):
            self.apply({'operation': 'set_evidence_sources', 'target': 'A1',
                        'paths': ['用药信息.药品名']})
        with self.assertRaisesRegex(ValueError, 'Unknown EMR path'):
            self.apply({'operation': 'set_evidence_sources', 'target': 'A1',
                        'paths': ['诊断.NotAField']})

    def test_noop_operation_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'produced no change'):
            self.apply({'operation': 'set_logic', 'target': 'DecisionLogic',
                        'logic_tree': {'or': ['A1', 'A2']}})

    def test_parameter_change_is_validated_and_preserves_sources(self):
        revised = self.apply({'operation': 'set_parameter', 'target': 'A1',
                              'parameter': 'match_values', 'value': ['Condition X', 'Condition Y']})
        binding = revised['constraint_bindings'][0]
        self.assertEqual(binding['function_parameters']['match_values'], ['Condition X', 'Condition Y'])
        self.assertEqual(binding['evidence_sources'], self.draft['constraint_bindings'][0]['evidence_sources'])

    def test_add_atom_requires_binding_and_updates_logic(self):
        incomplete = deepcopy(self.draft)
        incomplete['atomic_constraints'].pop()
        incomplete['constraint_bindings'].pop()
        incomplete['logic_tree'] = 'A1'
        operations = [
            {'operation': 'add_atom', 'target': 'A2',
             'atom': {'id': 'A2', 'normalized_constraint': 'Condition Y is established.',
                      'source_span': 'condition Y'},
             'binding': {'capability_id': 'clinical_text_semantic_assessment',
                         'parameters': self.draft['constraint_bindings'][1]['function_parameters'],
                         'paths': ['入院记录.现病史', '入院记录.既往史']}},
            {'operation': 'set_logic', 'target': 'DecisionLogic',
             'logic_tree': {'or': ['A1', 'A2']}},
        ]
        revised = service.apply_operations(incomplete, operations)
        revised.pop('_applied_operations', None)
        plan = compiled_plan_from_code(service.compile_draft(revised, self.irr).generated_code)
        self.assertEqual(plan['logic'], {'or': ['A1', 'A2']})
        self.assertEqual(len(plan['constraints']), 2)

    def test_request_revision_returns_only_actual_diff_and_operations(self):
        content = {'summary': 'Use the medication name field.', 'operations': [{
            'operation': 'replace_evidence_source', 'target': 'Applicability',
            'old_path': '用药信息.药品通用名', 'new_path': '用药信息.药品名',
        }]}
        client = self.model_client([content])
        before = deepcopy(self.draft)
        with patch.object(service.AgentAService, '_create_client', return_value=(client, 'test-model')):
            result = service.request_revision(
                self.draft, self.irr,
                'Applies when match the Medication name instead of Generic Drug Name.',
            )
        self.assertEqual(self.draft, before)
        self.assertEqual([item['section'] for item in result['changes']], ['applicability_binding'])
        self.assertEqual(result['operations'][0]['operation'], 'replace_evidence_source')
        self.assertEqual(result['summary'], content['summary'])

    def test_invalid_first_suggestion_gets_one_repair_attempt(self):
        first = {'summary': 'No effective change.', 'operations': [{
            'operation': 'set_logic', 'target': 'DecisionLogic',
            'logic_tree': {'or': ['A1', 'A2']},
        }]}
        second = {'summary': 'Corrected source.', 'operations': [{
            'operation': 'replace_evidence_source', 'target': 'Applicability',
            'old_path': '用药信息.药品通用名', 'new_path': '用药信息.药品名',
        }]}
        client = self.model_client([first, second])
        with patch.object(service.AgentAService, '_create_client', return_value=(client, 'test-model')):
            result = service.request_revision(
                self.draft, self.irr,
                'Applies when match the Medication name instead of Generic Drug Name.',
            )
        self.assertEqual(client.chat.completions.create.call_count, 2)
        self.assertEqual(result['changes'][0]['section'], 'applicability_binding')
        repair_messages = client.chat.completions.create.call_args.kwargs['messages']
        self.assertIn('failed deterministic validation', repair_messages[-1]['content'])

    def test_unrepresentable_revision_fails_instead_of_showing_identical_after(self):
        invalid = {'summary': 'Unchanged.', 'operations': [{
            'operation': 'set_logic', 'target': 'DecisionLogic',
            'logic_tree': {'or': ['A1', 'A2']},
        }]}
        client = self.model_client([invalid, invalid])
        with patch.object(service.AgentAService, '_create_client', return_value=(client, 'test-model')):
            with self.assertRaisesRegex(ValueError, 'could not be represented'):
                service.request_revision(
                    self.draft, self.irr,
                    'Applies when match the Medication name instead of Generic Drug Name.',
                )
        self.assertEqual(client.chat.completions.create.call_count, 2)

    def test_unknown_function_is_rejected(self):
        bad = deepcopy(self.draft)
        bad['constraint_bindings'][0]['audit_function'] = 'arbitrary_python'
        with self.assertRaisesRegex(ValueError, 'unregistered'):
            service.compile_draft(bad, self.irr)

    def test_endpoint_recompile_and_reload_keep_confirmed_plan(self):
        from rules.views import RuleViewSet
        rule = SimpleNamespace(type=self.irr['rule_category'], drug_name=self.irr['constraint_object'],
                               description=self.irr['constraint_condition'], rule_code='')
        view = RuleViewSet()
        view.get_object = lambda: rule
        response = view.recompile(SimpleNamespace(data={'draft': self.draft}), pk='test')
        self.assertEqual(response.status_code, 200)
        generated = response.data['result']
        rule.rule_code = generated['generated_code']
        loaded = view.compilation(SimpleNamespace(), pk='test')
        self.assertEqual(loaded.status_code, 200)
        for key in ('generated_code', 'atomic_constraints', 'logic_tree', 'constraint_bindings', 'readable_python'):
            self.assertEqual(loaded.data['result'][key], generated[key])

    @staticmethod
    def model_client(outputs):
        client = Mock()
        client.chat.completions.create.side_effect = [
            SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content=json.dumps(item, ensure_ascii=False)))])
            for item in outputs
        ]
        return client


if __name__ == '__main__':
    unittest.main()
