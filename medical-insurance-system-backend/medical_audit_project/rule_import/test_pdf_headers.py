"""PDF column preservation regressions; no model or database required."""
import unittest
from pathlib import Path
from django.conf import settings
from rule_import.services.extractor import extract_pdf_tables, rule_is_header


class PolicyHeaderTests(unittest.TestCase):
    def test_parenthetical_service_headers_are_headers(self):
        self.assertTrue(rule_is_header([
            '序号', '医疗服务项目A名称',
            '医疗服务项目A代码供参考（国家医保局全国医疗服务项目）',
            '检出逻辑', '逻辑依据（项目A项目内涵）', '备注',
        ]))

    def test_data_with_formulation_is_not_header(self):
        self.assertFalse(rule_is_header(['乙', '示例药品', '口服常释剂型', '(15)']))

    def test_sample_tables_retain_independent_headers(self):
        pdf = Path(__file__).resolve().parents[1] / 'Policy_Example.pdf'
        if not pdf.exists():
            self.skipTest('Sample PDF is unavailable')
        if not settings.configured:
            settings.configure(RULE_IMPORT_USE_LLM_HEADER_DETECTION=False)
        from unittest.mock import patch
        with patch.object(settings, 'RULE_IMPORT_USE_LLM_HEADER_DETECTION', False, create=True):
            tables = extract_pdf_tables(str(pdf))
        by_page = {table['source']['page']: table for table in tables}
        self.assertEqual(set(by_page), {1, 2, 3, 4})
        self.assertEqual(len(by_page[1]['rows']), 3)
        self.assertIn('检出逻辑', by_page[2]['rows'][0])
        self.assertIn('医疗服务项目A名称', by_page[2]['rows'][0])
        self.assertIn('医疗服务项目名称', by_page[3]['rows'][0])
        self.assertIn('频次上限', by_page[3]['rows'][0])
        self.assertIn('周期(天)', by_page[3]['rows'][0])
        self.assertIn('说明', by_page[4]['rows'][-1])
