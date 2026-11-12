import unittest
import json
from pathlib import Path

from .services.binding_resolver import (
    resolve_applicability_binding,
    resolve_constraint_bindings,
    materialize_binding,
)


class BindingRegressionTests(unittest.TestCase):
    def test_text_sources_reference_real_schema_fields(self):
        binding = materialize_binding(
            'clinical_text_semantic_assessment',
            {'evidence_scope': 'treatment_history', 'question': 'Is prior treatment documented?'},
            role='constraint',
            atom={'id': 'A1', 'normalized_constraint': 'Prior treatment is documented.'},
        )
        schema_path = Path(__file__).resolve().parents[3] / 'field.json'
        schema = json.loads(schema_path.read_text(encoding='utf-8'))
        self.assertGreater(binding['source_count'], 1)
        self.assertEqual(binding['source_count'], len(binding['evidence_sources']))
        for source in binding['evidence_sources']:
            section, field = source['path'].split('.', 1)
            self.assertIn(field, schema[section])
        self.assertEqual(
            binding['evidence_sources'], binding['runtime']['evidence_sources'],
        )

    def test_dosage_form_alias_does_not_include_bare_ingredient(self):
        binding = resolve_applicability_binding({
            'rule_category': '超限定用药',
            'constraint_object': '恩替卡韦口服溶液',
        })
        self.assertNotIn('恩替卡韦', binding['function_parameters']['match_values'])
        self.assertNotIn('Entecavir', binding['function_parameters']['match_values'])

    def test_distinct_diagnosis_concepts_keep_distinct_aliases(self):
        bindings = resolve_constraint_bindings([
            {'id': 'A1', 'normalized_constraint': 'The patient has chronic hepatitis B.', 'source_span': '慢性乙型肝炎'},
            {'id': 'A2', 'normalized_constraint': 'The patient has chronic HBV infection.', 'source_span': '慢性HBV感染'},
        ])
        adult = bindings[0]['function_parameters']['match_values']
        child = bindings[1]['function_parameters']['match_values']
        self.assertNotIn('慢性HBV感染', adult)
        self.assertNotIn('慢性乙型肝炎', child)
        self.assertIn('慢性乙型肝炎', adult)
        self.assertIn('慢性HBV感染', child)
