from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from feijian.services import alignment


class FeiJianAlignmentTests(SimpleTestCase):
    def test_category_alias_maps_to_canonical_category(self):
        canonical = next(iter(alignment.CATEGORY_ALIASES))
        alias = alignment.CATEGORY_ALIASES[canonical][0]

        self.assertEqual(alignment.canonical_category(alias), canonical)

    def test_text_similarity_handles_equivalent_text(self):
        self.assertGreaterEqual(
            alignment.text_similarity('A B C', 'ABC'),
            0.8,
        )

    def test_alignment_item_exposes_debug_fields(self):
        canonical = next(iter(alignment.CATEGORY_ALIASES))
        alias = alignment.CATEGORY_ALIASES[canonical][0]
        record = SimpleNamespace(
            id=1,
            audit_task_id='7',
            hospitalization_no='ZY001',
            patient_name='张三',
            hospital_name='测试医院',
            issue_category=alias,
            issue_description='',
            involved_amount=Decimal('10.00'),
        )
        result = SimpleNamespace(
            id=2,
            task_id=7,
            rule=SimpleNamespace(type=alias, drug_name='', description=''),
            reason=alias,
            violation_item='金额 10.00',
        )

        item = alignment._build_alignment(
            record,
            result,
            alignment.MATCHED,
            0.9,
            ['category matched'],
        )

        self.assertEqual(item['matchScore'], 0.9)
        self.assertEqual(item['feijianCategory'], canonical)
        self.assertEqual(item['systemCategory'], canonical)
        self.assertIn('matchDebug', item)
        self.assertEqual(item['matchDebug']['feijianNormalizedCategory'], canonical)
        self.assertEqual(item['matchDebug']['systemNormalizedCategory'], canonical)
