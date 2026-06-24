"""规则批量导入转换 - Celery 异步任务

复用项目现有异步机制（Celery + Redis，见 tasks/tasks.py 范式）：
  - 开头 close_old_connections() 避免长连接失效
  - 分阶段回写 status / stage / progress
  - 全程日志
  - 所有异常落 error_detail，任务置 failed
  - soft_time_limit 控制超长任务
"""

import logging

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from .models import RuleImportTask
from .services.facade import extract_rules_from_file
from .services.importer import save_extracted_rules

logger = logging.getLogger(__name__)


def _update(task, **fields):
    """局部更新任务字段并保存（带 updated_at）。"""
    for k, v in fields.items():
        setattr(task, k, v)
    if 'updated_at' not in fields:
        fields['updated_at'] = timezone.now()
        task.updated_at = fields['updated_at']
    task.save(update_fields=list(fields.keys()))


@shared_task(
    bind=True,
    soft_time_limit=getattr(settings, 'RULE_IMPORT_TASK_SOFT_TIME_LIMIT', 3600),
    time_limit=getattr(settings, 'RULE_IMPORT_TASK_TIME_LIMIT', 3900),
)
def run_rule_import_task(self, task_id):
    """执行单个规则导入转换任务。"""
    close_old_connections()
    logger.info("[rule_import] 开始执行任务 %s", task_id)

    try:
        task = RuleImportTask.objects.get(pk=task_id)
    except RuleImportTask.DoesNotExist:
        logger.error("[rule_import] 任务 %s 不存在", task_id)
        return {"error": "task not found"}

    if not task.original_file:
        _update(task, status=RuleImportTask.Status.FAILED,
                error_detail="任务缺少原始文件，无法执行")
        return {"error": "no file"}

    params = task.params or {}
    file_path = task.original_file.path

    # 进度回调：解析完成 / 抽取进度
    def parse_cb(table_count):
        _update(task, stage='parse', table_count=table_count, progress=20)

    def progress_cb(done, total, found):
        # 抽取阶段占 20% ~ 95%
        pct = 20 + int((done / total) * 75) if total else 20
        _update(task, stage='extract', progress=min(pct, 95),
                rule_count=found)

    try:
        _update(task, status=RuleImportTask.Status.PARSING, stage='parse',
                progress=5, started_at=timezone.now(),
                celery_task_id=str(self.request.id or ''))

        # 数量类参数为 None 时表示不限数量(全部)；分块行数回退到后端配置
        result = extract_rules_from_file(
            file_path=file_path,
            max_pdf_pages=params.get('max_pdf_pages'),
            max_rows_per_table=params.get('max_rows_per_table'),
            chunk_size=params.get('chunk_size')
            or getattr(settings, 'RULE_IMPORT_DEFAULT_CHUNK_SIZE', 10),
            max_tables=params.get('max_tables'),
            parse_cb=parse_cb,
            progress_cb=progress_cb,
        )

        _update(task, status=RuleImportTask.Status.EXTRACTING, stage='extract',
                progress=96)

        # 输出解析：落暂存表
        saved = save_extracted_rules(task, result['rules'])

        _update(task,
                status=RuleImportTask.Status.SUCCESS,
                stage='done',
                progress=100,
                table_count=result['table_count'],
                rule_count=saved,
                finished_at=timezone.now(),
                error_detail='')
        logger.info("[rule_import] 任务 %s 完成: %s 表 / %s 规则",
                    task_id, result['table_count'], saved)
        return {"task_id": task_id, "table_count": result['table_count'],
                "rule_count": saved}

    except SoftTimeLimitExceeded:
        logger.error("[rule_import] 任务 %s 执行超时", task_id)
        _update(task, status=RuleImportTask.Status.FAILED, stage='extract',
                error_detail="任务执行超时(SoftTimeLimitExceeded)，请减少处理页数/表数后重试",
                finished_at=timezone.now())
        return {"error": "timeout"}

    except Exception as e:  # noqa: BLE001 - 兜底所有异常，保证可观测
        logger.exception("[rule_import] 任务 %s 执行失败", task_id)
        _update(task, status=RuleImportTask.Status.FAILED,
                error_detail=str(e)[:2000], finished_at=timezone.now())
        return {"error": str(e)}
    finally:
        close_old_connections()
