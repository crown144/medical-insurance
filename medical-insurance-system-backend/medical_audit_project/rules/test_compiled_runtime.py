import json
import ast
import unittest
from types import SimpleNamespace
from unittest import mock

from django.conf import settings

if not settings.configured:
    settings.configure(
        SECRET_KEY='test-only', INSTALLED_APPS=['rules', 'pricings'],
        DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
    )
    import django
    django.setup()

from engine import compiled_runtime
from engine.over_standard_v2 import execute_db_rules
from rules.services.binding_resolver import materialize_binding
from rules.services.deterministic_compiler import compile_rule
from rules.services.readable_renderer import compiled_plan_from_code, render_readable_python


class CompiledRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.app = materialize_binding(
            'medication_name_matching', {'operator': 'contains', 'match_values': ['Drug X']},
            role='applicability', object_text='Drug X',
        )
        self.atom = materialize_binding(
            'diagnosis_name_matching', {'operator': 'contains', 'match_values': ['Condition X']},
            role='constraint', atom={'id': 'A1', 'normalized_constraint': 'Condition X is documented.'},
        )
        self.text = materialize_binding(
            'clinical_text_semantic_assessment',
            {'evidence_scope': 'clinical_narrative', 'question': 'Is condition Y established?'},
            role='constraint', atom={'id': 'A2', 'normalized_constraint': 'Condition Y is established.'},
        )
        self.case = {'用药信息': [{'药品通用名': 'Drug X'}],
                     '诊断': [{'诊断名称': 'Condition X'}],
                     '入院记录': {'现病史': 'Condition Y is present.'}}

    def test_schema_validated_multisource_binding(self):
        code = compile_rule({'or': ['A1', 'A2']}, self.app, [self.atom, self.text])
        self.assertIn('execute_compiled_plan', code)
        self.assertGreater(self.text['source_count'], 1)
        self.assertIn('入院记录.现病史', [item['path'] for item in self.text['evidence_sources']])

    def test_readable_preview_is_derived_from_actual_plan(self):
        logic = {'or': [{'and': ['A1', 'A2']}, {'not': ['A1']}]}
        code = compile_rule(logic, self.app, [self.atom, self.text])
        plan = compiled_plan_from_code(code)
        preview = render_readable_python(plan)
        ast.parse(preview)
        self.assertEqual(plan['logic'], logic)
        self.assertEqual(preview, render_readable_python(plan))
        self.assertIn('def check_applicability():', preview)
        self.assertIn('lazy_any(', preview)
        self.assertIn('lazy_all(', preview)
        self.assertIn('logical_not(', preview)
        for binding in plan['constraints']:
            self.assertIn(f"atomic_id={binding['atomic_constraint_id']!r}", preview)
            for source in binding['evidence_sources']:
                self.assertIn(source['path'], preview)
        self.assertIn("audit_function='llm_bool'", preview)
        self.assertNotIn(repr(plan), preview)
        self.assertLess(max(map(len, preview.splitlines())), 200)

    def test_preview_orders_branches_like_the_executor(self):
        logic = {'or': ['A2', 'A1']}
        plan = compiled_plan_from_code(compile_rule(logic, self.app, [self.atom, self.text]))
        preview = render_readable_python(plan)
        section = preview.split('decision = evaluate_logic(', 1)[1]
        self.assertLess(section.index('# Alternative branch 2'), section.index('# Alternative branch 1'))
        self.assertLess(section.index('check_atom_1()'), section.index('check_atom_2()'))

    def test_lazy_or_skips_text_and_returns_highlights(self):
        plan = {'logic': {'or': ['A1', 'A2']}, 'applicability': self.app,
                'constraints': [self.atom, self.text]}
        with mock.patch.object(compiled_runtime, 'llm_evidence') as llm:
            result = compiled_runtime.execute_compiled_plan(self.case, plan)
        llm.assert_not_called()
        self.assertEqual(result['review_status'], 'compliant')
        self.assertEqual(result['evidence']['skipped_atomic_ids'], ['A2'])
        self.assertTrue(any('诊断名称' in item['field_path'] for item in result['evidence']['highlights']))

    def test_insufficient_text_is_review_not_violation(self):
        plan = {'logic': 'A2', 'applicability': self.app, 'constraints': [self.text]}
        stub = {'value': False, 'insufficient_evidence': True, 'evidence': [], 'reason': 'Unknown'}
        with mock.patch.object(compiled_runtime, 'llm_evidence', return_value=stub):
            result = compiled_runtime.execute_compiled_plan(self.case, plan)
        self.assertEqual(result['review_status'], 'needs_review')
        self.assertEqual(result['evidence']['insufficient_atomic_ids'], ['A2'])

    def test_inapplicability_skips_all_conditions(self):
        plan = {'logic': 'A2', 'applicability': self.app, 'constraints': [self.text]}
        case = {'用药信息': [{'药品通用名': 'Other Drug'}]}
        with mock.patch.object(compiled_runtime, 'llm_evidence') as llm:
            result = compiled_runtime.execute_compiled_plan(case, plan)
        llm.assert_not_called()
        self.assertEqual(result['review_status'], 'not_applicable')
        self.assertEqual(result['evidence']['skipped_atomic_ids'], ['A2'])

    def test_explicit_negative_text_produces_violation_and_highlight(self):
        plan = {'logic': 'A2', 'applicability': self.app, 'constraints': [self.text]}
        stub = {'value': False, 'insufficient_evidence': False,
                'evidence': [{'source_path': '入院记录.现病史', 'text': 'Condition Y is present.'}],
                'reason': 'Explicit negative finding.'}
        with mock.patch.object(compiled_runtime, 'llm_evidence', return_value=stub):
            result = compiled_runtime.execute_compiled_plan(self.case, plan)
        self.assertEqual(result['review_status'], 'violation')
        self.assertIn('A2', result['evidence']['failed_atomic_ids'])
        self.assertTrue(any('入院记录.现病史' in item['field_path'] for item in result['evidence']['highlights']))

    def test_failed_or_explains_only_selected_branch(self):
        missing = materialize_binding(
            'diagnosis_name_matching', {'operator': 'contains', 'match_values': ['Condition Z']},
            role='constraint', atom={'id': 'A3', 'normalized_constraint': 'Condition Z is documented.'},
        )
        plan = {'logic': {'or': ['A3', {'and': ['A1', 'A2']}]},
                'applicability': self.app, 'constraints': [self.atom, self.text, missing]}
        stub = {'value': False, 'insufficient_evidence': False, 'evidence': [], 'reason': 'No evidence.'}
        with mock.patch.object(compiled_runtime, 'llm_evidence', return_value=stub):
            result = compiled_runtime.execute_compiled_plan(self.case, plan)
        self.assertEqual(result['evidence']['failed_atomic_ids'], ['A2'])
        self.assertNotIn('A3', result['failure_message'])

    def test_actual_executor_runs_generated_program(self):
        code = compile_rule('A1', self.app, [self.atom])
        rule = SimpleNamespace(rule_code=code, rule_id='test-rule', drug_name='Drug X',
                               type='超限定用药', description='Test rule')
        self.assertEqual(execute_db_rules(self.case, '超限定用药', [rule]), [])

    def test_actual_executor_returns_review_without_violation(self):
        code = compile_rule('A2', self.app, [self.text])
        rule = SimpleNamespace(rule_code=code, rule_id='test-rule', drug_name='Drug X',
                               type='超限定用药', description='Test rule')
        stub = {'value': False, 'insufficient_evidence': True, 'evidence': [], 'reason': 'Unknown'}
        with mock.patch.object(compiled_runtime, 'llm_evidence', return_value=stub):
            results = execute_db_rules(self.case, '超限定用药', [rule])
        self.assertEqual(results[0]['review_status'], 'needs_review')
        self.assertIsNone(results[0]['passed'])
        self.assertFalse(results[0]['violation'])

    def test_violation_snapshot_preserves_checked_records_and_applicability(self):
        code = compile_rule('A1', self.app, [self.atom])
        rule = SimpleNamespace(rule_code=code, rule_id='test-rule', drug_name='Drug X',
                               type='超限定用药', description='Test rule')
        case = {'用药信息': [{'药品通用名': 'Drug X'}],
                '诊断': [{'诊断名称': 'Condition Z'}, {'诊断名称': 'Condition W'}]}
        results = execute_db_rules(case, '超限定用药', [rule])
        evidence = results[0]['item']['audit_evidence']
        self.assertEqual(evidence['failed_atomic_ids'], ['A1'])
        self.assertEqual(evidence['atomic_results']['A1']['normalized_constraint'],
                         'Condition X is documented.')
        self.assertEqual(evidence['atomic_results']['A1']['checked_records'], [
            {'source_path': '诊断[0].诊断名称', 'text': 'Condition Z'},
            {'source_path': '诊断[1].诊断名称', 'text': 'Condition W'},
        ])
        self.assertEqual(evidence['applicability']['evidence'][0]['text'], 'Drug X')

    def test_not_explains_a_prohibited_match(self):
        plan = {'logic': {'not': ['A1']}, 'applicability': self.app, 'constraints': [self.atom]}
        result = compiled_runtime.execute_compiled_plan(self.case, plan)
        self.assertEqual(result['review_status'], 'violation')
        self.assertEqual(result['evidence']['failed_atomic_ids'], ['A1'])
        self.assertIn('prohibited condition', result['failure_message'])

    def test_existing_single_field_binding_can_compile(self):
        atom = dict(self.atom)
        atom.pop('evidence_sources', None)
        atom['runtime'] = dict(atom['runtime'])
        atom['runtime'].pop('evidence_sources', None)
        code = compile_rule('A1', self.app, [atom])
        namespace = {'execute_compiled_plan': compiled_runtime.execute_compiled_plan,
                     'submit_result': lambda **result: result}
        exec(code, namespace)
        result = namespace['execute_rule'](self.case)
        self.assertEqual(result['review_status'], 'compliant')

    def test_unrecognized_physical_path_is_rejected(self):
        binding = dict(self.atom, evidence_sources=[{'path': '入院记录.虚构字段'}])
        with self.assertRaisesRegex(ValueError, 'Unknown EMR path'):
            compile_rule('A1', self.app, [binding])

    def test_diagnosis_code_binding_uses_icd10_field(self):
        binding = materialize_binding(
            'list_membership', {'expected_values': ['K21']}, role='constraint',
            atom={'id': 'A1', 'normalized_constraint': 'Diagnosis code includes K21.'},
        )
        self.assertEqual(binding['evidence_sources'][0]['path'], '诊断.ICD10编码')
        code = compile_rule('A1', self.app, [binding])
        namespace = {'execute_compiled_plan': compiled_runtime.execute_compiled_plan,
                     'submit_result': lambda **result: result}
        exec(code, namespace)
        result = namespace['execute_rule']({
            '用药信息': [{'药品通用名': 'Drug X'}],
            '诊断': [{'ICD10编码': 'K21'}],
        })
        self.assertEqual(result['review_status'], 'compliant')
        self.assertEqual(result['evidence']['atomic_results']['A1']['evidence'][0]['source_path'],
                         '诊断[0].ICD10编码')

    def test_quoted_llm_evidence_is_verified(self):
        answer = {'status': 'satisfied', 'quote': 'invented', 'source_path': '入院记录.现病史'}
        response = mock.Mock()
        response.json.return_value = {'choices': [{'message': {'content': json.dumps(answer)}}]}
        with mock.patch.object(compiled_runtime.requests, 'post', return_value=response):
            result = compiled_runtime.llm_evidence([{'path': '入院记录.现病史', 'text': 'actual'}], 'Question?')
        self.assertTrue(result['insufficient_evidence'])
        self.assertEqual(result['evidence'], [])
