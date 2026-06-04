import os
from django.test import TestCase

from repeat_charging.father_child_detector import FatherChildDuplicateDetector
from repeat_charging.models import ParentChildRelation


class FatherChildDetectorTests(TestCase):
    def setUp(self):
        ParentChildRelation.objects.create(
            parent_insurance_code='P001',
            parent_charge_code='A123',
            parent_name='父项目A',
            child_insurance_code='C001',
            child_charge_code='B456',
            child_name='子项目B',
        )

        self.patient_json = {
            '患者住院号': 'ZY0001',
            '收费报告': [
                {
                    '收费项目代码': 'A123',
                    '收费项目名称': '父项目A',
                    '收费日期': '2024-10-16 09:20:00',
                    '项目单价': 100,
                    '数量': 1,
                    'ORDER_ITEM_CODE': 'ORD001'
                },
                {
                    '收费项目代码': 'B456',
                    '收费项目名称': '子项目B',
                    '收费日期': '2024-10-16 10:05:00',
                    '项目单价': 50,
                    '数量': 2,
                    'ORDER_ITEM_CODE': 'ORD002'
                }
            ]
        }

    def test_detects_father_child_duplicate(self):
        detector = FatherChildDuplicateDetector()
        violations = detector.detect(self.patient_json)

        self.assertTrue(len(violations) >= 1)
        v = violations[0]
        self.assertTrue(v.get('violation'))
        self.assertEqual(v['rule']['type'], '重复收费-父子')
        self.assertEqual(v['item']['患者住院号'], 'ZY0001')
        self.assertIn('总金额', v['item'])
        self.assertTrue(v.get('highlights'))