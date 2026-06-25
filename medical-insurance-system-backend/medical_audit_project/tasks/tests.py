from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory

from .inhos_views import InhosNumbersAPIView, QueryParameterError, _build_query


@override_settings(
    SOURCE_MDC_ORG_CD='5605',
    INHOS_QUERY_MAX_MONTHS=3,
    INHOS_QUERY_MAX_RESULTS=2,
)
class InhosNumbersAPIViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_date_query_uses_ods_table_org_and_raw_datetime_range(self):
        request = self.factory.get('/api/inhos-numbers/', {'start_date': '2026-01'})
        sql, params, filter_type, _, _ = _build_query(request)

        self.assertIn('ods_fact_mdc_rcd_hmpg', sql)
        self.assertIn('h.MDC_ORG_CD = :mdc_org_cd', sql)
        self.assertIn('h.DSCG_DT_TM >= :start_datetime', sql)
        self.assertNotIn('DATE_FORMAT', sql)
        self.assertEqual(params['mdc_org_cd'], '5605')
        self.assertEqual(params['end_datetime'].month, 2)
        self.assertEqual(filter_type, 'date_only')

    def test_date_and_drug_query_joins_ods_tables(self):
        request = self.factory.get('/api/inhos-numbers/', {
            'start_date': '2026-01',
            'end_date': '2026-02',
            'drug_name': '阿司匹林',
        })
        sql, params, filter_type, _, _ = _build_query(request)

        self.assertIn('ods_fact_mdc_rcd_hmpg', sql)
        self.assertIn('ods_fact_trtmt_dos_rcd', sql)
        self.assertIn('ON t.INHOS_NO = h.INHOS_NO', sql)
        self.assertEqual(params['drug_name'], '%阿司匹林%')
        self.assertIn('t.MDC_ORG_CD = h.MDC_ORG_CD', sql)
        self.assertEqual(filter_type, 'date_and_drug')

    def test_request_mdc_org_cd_overrides_default_org(self):
        request = self.factory.get('/api/inhos-numbers/', {
            'drug_name': '阿司匹林',
            'mdc_org_cd': '9911',
        })
        sql, params, filter_type, _, _ = _build_query(request)

        self.assertIn('t.MDC_ORG_CD = :mdc_org_cd', sql)
        self.assertEqual(params['mdc_org_cd'], '9911')
        self.assertEqual(filter_type, 'drug_only')

    def test_rejects_ranges_over_configured_limit(self):
        request = self.factory.get('/api/inhos-numbers/', {
            'start_date': '2026-01',
            'end_date': '2026-04',
        })
        with self.assertRaises(QueryParameterError):
            _build_query(request)

    @patch('tasks.inhos_views._execute_query', return_value=(['A', 'B'], True))
    def test_success_response_uses_request_client_envelope(self, _execute):
        request = self.factory.get('/api/inhos-numbers/', {'drug_name': '阿司匹林'})
        response = InhosNumbersAPIView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['code'], 0)
        self.assertTrue(response.data['result']['truncated'])
        self.assertEqual(response.data['result']['limit'], 2)
        self.assertIn('warning', response.data['result'])
