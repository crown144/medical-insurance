"""rule_import 基础接口与服务测试

策略：不触网、不依赖 pdfplumber/LLM。
  - 上传接口：mock 掉 Celery 投递，只验证参数校验与建任务
  - 输出解析/入库：直接喂算法输出的数据结构，验证落库与映射
运行：
    python manage.py test rule_import
"""

import tempfile
from unittest import mock

from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient

from rules.models import Rule

from .models import ExtractedRule, RuleImportTask
from .services.importer import (
    RULE_TYPE_MAP,
    import_to_rule_library,
    save_extracted_rules,
)

_MEDIA = tempfile.mkdtemp(prefix='ruleimport_test_media_')

SAMPLE_RULES = [
    {
        "rule_id": 1,
        "rule_type": "DRUG_RESTRICTION",
        "constrained_object": "艾普拉唑",
        "constraint_value": "限有十二指肠溃疡、反流性食管炎诊断患者的二线用药",
        "evidence": {"编号": "17", "药品名称": "艾普拉唑"},
        "source": {"file_name": "药品目录.pdf", "page": 9, "table_index": 0},
    },
    {
        "rule_id": 2,
        "rule_type": "DUPLICATE_CHARGE",
        "constrained_object": "胃肠减压",
        "constraint_value": "插胃管与胃肠减压不得同时收费",
        "evidence": {"项目名称": "胃肠减压"},
        "source": {"file_name": "收费项目.pdf", "page": 3, "table_index": 1},
    },
]


@override_settings(MEDIA_ROOT=_MEDIA)
class UploadApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @mock.patch('rule_import.views.run_rule_import_task.delay')
    def test_upload_valid_excel_creates_task(self, mock_delay):
        from django.conf import settings
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile(
            '药品目录.xlsx', b'fake-excel-bytes',
            content_type='application/vnd.ms-excel',
        )
        resp = self.client.post('/api/rule-import/upload/',
                                {'file': f}, format='multipart')
        self.assertEqual(resp.status_code, 201)
        self.assertIn('task', resp.data)
        task_id = resp.data['task']['id']
        task = RuleImportTask.objects.get(pk=task_id)
        self.assertEqual(task.file_type, 'xlsx')
        # chunk_size 仅由后端配置决定（前端不再传）
        self.assertEqual(task.params['chunk_size'],
                         settings.RULE_IMPORT_DEFAULT_CHUNK_SIZE)
        # 数量类参数不传 = 不限数量(None)
        self.assertIsNone(task.params['max_pdf_pages'])
        self.assertIsNone(task.params['max_rows_per_table'])
        self.assertIsNone(task.params['max_tables'])
        self.assertEqual(task.status, RuleImportTask.Status.PENDING)
        mock_delay.assert_called_once_with(task_id)

    def test_upload_rejects_bad_extension(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile('rules.txt', b'hello', content_type='text/plain')
        resp = self.client.post('/api/rule-import/upload/',
                                {'file': f}, format='multipart')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.data)

    def test_upload_requires_file(self):
        resp = self.client.post('/api/rule-import/upload/', {}, format='multipart')
        self.assertEqual(resp.status_code, 400)


@override_settings(MEDIA_ROOT=_MEDIA)
class OutputParsingTests(TestCase):
    def test_save_extracted_rules(self):
        task = RuleImportTask.objects.create(task_name='t1')
        n = save_extracted_rules(task, SAMPLE_RULES)
        self.assertEqual(n, 2)
        self.assertEqual(task.rules.count(), 2)
        first = task.rules.order_by('seq').first()
        self.assertEqual(first.rule_type, 'DRUG_RESTRICTION')
        self.assertEqual(first.constrained_object, '艾普拉唑')

    def test_save_is_idempotent_on_rerun(self):
        task = RuleImportTask.objects.create(task_name='t2')
        save_extracted_rules(task, SAMPLE_RULES)
        save_extracted_rules(task, SAMPLE_RULES)  # 重跑应先清空
        self.assertEqual(task.rules.count(), 2)


@override_settings(MEDIA_ROOT=_MEDIA)
class ConfirmImportTests(TestCase):
    def setUp(self):
        self.task = RuleImportTask.objects.create(
            task_name='t3', status=RuleImportTask.Status.SUCCESS,
        )
        save_extracted_rules(self.task, SAMPLE_RULES)

    def test_import_selected_to_rule_library(self):
        first = self.task.rules.order_by('seq').first()
        result = import_to_rule_library(self.task, rule_ids=[first.id])
        self.assertEqual(result['imported'], 1)
        self.assertEqual(Rule.objects.count(), 1)
        rule = Rule.objects.first()
        # 英文枚举映射为中文类型
        self.assertEqual(rule.type, RULE_TYPE_MAP['DRUG_RESTRICTION'])
        self.assertEqual(rule.drug_name, '艾普拉唑')
        first.refresh_from_db()
        self.assertTrue(first.is_imported)
        self.assertEqual(first.imported_rule_id, rule.rule_id)

    def test_import_select_all(self):
        result = import_to_rule_library(self.task, select_all=True)
        self.assertEqual(result['imported'], 2)
        self.assertEqual(Rule.objects.count(), 2)
        self.task.refresh_from_db()
        self.assertEqual(self.task.imported_count, 2)

    def test_import_is_idempotent(self):
        import_to_rule_library(self.task, select_all=True)
        # 第二次：已入库的不再重复
        result = import_to_rule_library(self.task, select_all=True)
        self.assertEqual(result['imported'], 0)
        self.assertEqual(Rule.objects.count(), 2)


@override_settings(MEDIA_ROOT=_MEDIA)
class TaskApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.task = RuleImportTask.objects.create(
            task_name='api-task', status=RuleImportTask.Status.SUCCESS,
            table_count=2, rule_count=2,
        )
        save_extracted_rules(self.task, SAMPLE_RULES)

    def test_list_tasks_paginated(self):
        resp = self.client.get('/api/rule-import/tasks/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('results', resp.data)
        self.assertGreaterEqual(resp.data['count'], 1)

    def test_task_detail_for_polling(self):
        resp = self.client.get(f'/api/rule-import/tasks/{self.task.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'success')
        self.assertIn('progress', resp.data)

    def test_extracted_rules_endpoint(self):
        resp = self.client.get(f'/api/rule-import/tasks/{self.task.id}/rules/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 2)

    def test_extracted_rules_filter_by_type(self):
        resp = self.client.get(
            f'/api/rule-import/tasks/{self.task.id}/rules/',
            {'rule_type': 'DUPLICATE_CHARGE'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)

    def test_confirm_requires_selection(self):
        resp = self.client.post(
            f'/api/rule-import/tasks/{self.task.id}/confirm/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_confirm_select_all(self):
        resp = self.client.post(
            f'/api/rule-import/tasks/{self.task.id}/confirm/',
            {'select_all': True}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['imported'], 2)

    def test_confirm_blocked_when_not_success(self):
        pending = RuleImportTask.objects.create(
            task_name='pending', status=RuleImportTask.Status.PENDING)
        resp = self.client.post(
            f'/api/rule-import/tasks/{pending.id}/confirm/',
            {'select_all': True}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_download_json(self):
        resp = self.client.get(
            f'/api/rule-import/tasks/{self.task.id}/download/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('attachment', resp['Content-Disposition'])


@override_settings(MEDIA_ROOT=_MEDIA)
class CeleryTaskTests(TransactionTestCase):
    """run_rule_import_task 的状态机/异常/超时验证（mock 算法层，不触网）。

    用 TransactionTestCase：任务内 close_old_connections() 会关闭连接，
    与 TestCase 的外层 atomic 包裹冲突，故需真实提交的事务模型。
    """

    def _make_task_with_file(self):
        from django.core.files.base import ContentFile
        task = RuleImportTask.objects.create(
            task_name='celery', file_name='x.xlsx', file_type='xlsx',
            params={'chunk_size': 20},
        )
        task.original_file.save('x.xlsx', ContentFile(b'dummy'), save=True)
        return task

    @mock.patch('rule_import.tasks.extract_rules_from_file')
    def test_task_success_path(self, mock_extract):
        mock_extract.return_value = {
            'tables': [], 'rules': SAMPLE_RULES, 'table_count': 2, 'rule_count': 2,
        }
        task = self._make_task_with_file()
        from .tasks import run_rule_import_task
        run_rule_import_task.apply(args=[task.id])
        task.refresh_from_db()
        self.assertEqual(task.status, RuleImportTask.Status.SUCCESS)
        self.assertEqual(task.progress, 100)
        self.assertEqual(task.rule_count, 2)
        self.assertIsNotNone(task.finished_at)
        self.assertEqual(task.rules.count(), 2)

    @mock.patch('rule_import.tasks.extract_rules_from_file')
    def test_task_failure_saves_error(self, mock_extract):
        mock_extract.side_effect = ValueError('boom-parse-error')
        task = self._make_task_with_file()
        from .tasks import run_rule_import_task
        run_rule_import_task.apply(args=[task.id])
        task.refresh_from_db()
        self.assertEqual(task.status, RuleImportTask.Status.FAILED)
        self.assertIn('boom-parse-error', task.error_detail)
        self.assertIsNotNone(task.finished_at)

    @mock.patch('rule_import.tasks.extract_rules_from_file')
    def test_task_timeout_saves_error(self, mock_extract):
        from celery.exceptions import SoftTimeLimitExceeded
        mock_extract.side_effect = SoftTimeLimitExceeded()
        task = self._make_task_with_file()
        from .tasks import run_rule_import_task
        run_rule_import_task.apply(args=[task.id])
        task.refresh_from_db()
        self.assertEqual(task.status, RuleImportTask.Status.FAILED)
        self.assertIn('超时', task.error_detail)

    def test_task_missing_file_fails(self):
        task = RuleImportTask.objects.create(task_name='nofile')
        from .tasks import run_rule_import_task
        run_rule_import_task.apply(args=[task.id])
        task.refresh_from_db()
        self.assertEqual(task.status, RuleImportTask.Status.FAILED)
        self.assertIn('文件', task.error_detail)


@override_settings(MEDIA_ROOT=_MEDIA)
class ConcurrencyTests(TestCase):
    """并发/重复上传：同名文件不应互相覆盖。"""

    @mock.patch('rule_import.views.run_rule_import_task.delay')
    def test_same_filename_no_overwrite(self, _mock_delay):
        from django.core.files.uploadedfile import SimpleUploadedFile
        client = APIClient()
        paths = []
        for _ in range(2):
            f = SimpleUploadedFile('药品目录.xlsx', b'data-bytes',
                                   content_type='application/vnd.ms-excel')
            resp = client.post('/api/rule-import/upload/',
                               {'file': f}, format='multipart')
            self.assertEqual(resp.status_code, 201)
            tid = resp.data['task']['id']
            paths.append(RuleImportTask.objects.get(pk=tid).original_file.name)
        # Django Storage 自动加随机后缀，两次存储路径不同
        self.assertNotEqual(paths[0], paths[1])
