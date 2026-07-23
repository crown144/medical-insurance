from io import BytesIO
import json
from unittest.mock import patch
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient, APIRequestFactory

from accounts.auth import build_access_token
from accounts.models import AccountProfile
from cases.models import Case
from .inhos_views import InhosNumbersAPIView, QueryParameterError, _build_query
from .models import Task


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

class CaseStorageMappingTests(SimpleTestCase):
    def test_case_model_maps_to_cases_case(self):
        self.assertEqual(Case._meta.db_table, 'cases_case')



class TaskCaseDownloadTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user = get_user_model().objects.create_user(
            username='developer-download', password='password'
        )
        AccountProfile.objects.create(
            user=user, role=AccountProfile.Role.DEVELOPER
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {build_access_token(user)}'
        )
        self.task = Task.objects.create(
            name='任务病历下载测试',
            hospitalization_ids=['ZY001', 'ZY002'],
            mdc_org_cd='460000000228',
        )

    def _create_task_case(self, hospitalization_id):
        Case.objects.create(
            hospitalization_id=f'{self.task.mdc_org_cd}:{hospitalization_id}',
            json_content={'住院号': hospitalization_id},
        )

    def test_downloads_task_cases_as_zip_without_violations(self):
        self._create_task_case('ZY001')
        self._create_task_case('ZY002')

        response = self.client.get(
            f'/api/tasks/{self.task.id}/download-result-cases/'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')
        with ZipFile(BytesIO(response.content)) as archive:
            self.assertEqual(sorted(archive.namelist()), ['ZY001.json', 'ZY002.json'])

    def test_rejects_downloads_over_twenty_task_cases(self):
        self.task.hospitalization_ids = [f'ZY{index:03d}' for index in range(21)]
        self.task.save(update_fields=['hospitalization_ids'])

        response = self.client.get(
            f'/api/tasks/{self.task.id}/download-result-cases/'
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('最多允许下载 20 份', response.data['error'])

    @patch('tasks.views.get_patient_data', return_value={'住院号': 'ZY001'})
    def test_fetches_uncached_task_case_without_violations(self, get_patient_data_mock):
        self.task.hospitalization_ids = ['ZY001']
        self.task.save(update_fields=['hospitalization_ids'])

        response = self.client.get(
            f'/api/tasks/{self.task.id}/download-result-cases/'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json; charset=utf-8')
        self.assertEqual(json.loads(response.content), {'住院号': 'ZY001'})
        get_patient_data_mock.assert_called_once_with('ZY001', self.task.mdc_org_cd)

    @override_settings(SOURCE_MDC_ORG_CD='5605')
    def test_uses_default_org_code_for_cached_legacy_task(self):
        self.task.mdc_org_cd = ''
        self.task.hospitalization_ids = ['ZY001']
        self.task.save(update_fields=['mdc_org_cd', 'hospitalization_ids'])
        Case.objects.create(
            hospitalization_id='5605:ZY001',
            json_content={'住院号': 'ZY001'},
        )

        response = self.client.get(
            f'/api/tasks/{self.task.id}/download-result-cases/'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), {'住院号': 'ZY001'})
