from django.test import SimpleTestCase

from .views import (
    _SOURCE_SYSTEM,
    _build_charge_item_id,
    _build_clue_prompt,
    _build_external_clue_id,
    _merge_clues,
)


class CluePayloadTests(SimpleTestCase):
    def test_item_id_includes_full_charge_time_and_record_identity(self):
        item_id = _build_charge_item_id(
            'YBDR0010',
            '460000000228',
            'ZY090000375036',
            'Y00000013061',
            '2025-02-07 11:21:30',
            'Y00000013061',
            3,
            42,
        )

        self.assertIn('20250207112130', item_id)
        self.assertTrue(item_id.endswith('_Y00000013061_3_42'))

    def test_external_clue_uses_registered_source_system_code(self):
        self.assertEqual(_SOURCE_SYSTEM, 'THREE_MEDICAL_REG_EVAL')
        self.assertEqual(
            _build_external_clue_id('YBDR0010', '460000000228', 'ZY090000375036'),
            'THREE_MEDICAL_REG_EVAL_YBDR0010_460000000228_ZY090000375036',
        )

    def test_clue_prompt_starts_with_hospitalization_id(self):
        self.assertEqual(
            _build_clue_prompt('ZY090000375036', '适应症不符'),
            'ZY090000375036_适应症不符',
        )

    def test_merge_keeps_all_evidence_when_item_ids_collide(self):
        merged = _merge_clues([{
            'externalClueId': 'THREE_MEDICAL_REG_EVAL_YBDR0010_460000000228_ZY1',
            'clueEvidence': [{'itemId': 'charge-1'}, {'itemId': 'charge-1'}],
            'evidenceCount': 2,
            'evidenceType': 'MULTIPLE',
        }])

        self.assertEqual(merged[0]['evidenceCount'], 2)
        self.assertEqual(merged[0]['evidenceType'], 'MULTIPLE')
        self.assertEqual(
            [item['itemId'] for item in merged[0]['clueEvidence']],
            ['charge-1', 'charge-1_2'],
        )
