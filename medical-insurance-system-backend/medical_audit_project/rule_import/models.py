# rule_import/models.py
from django.db import models


class RuleImportTask(models.Model):
    """规则批量导入转换任务

    复用 feijian.FeiJianImportBatch / tasks.Task 的状态机风格：
    用户上传药品/收费目录文件后，由 Celery 异步执行
    “文件解析 -> LLM 规则抽取”，过程与结果记录在本表。
    """
    class Status(models.TextChoices):
        PENDING = 'pending', '待处理'
        PARSING = 'parsing', '解析中'
        EXTRACTING = 'extracting', '抽取中'
        SUCCESS = 'success', '转换成功'
        FAILED = 'failed', '转换失败'
        CANCELED = 'canceled', '已取消'

    task_name = models.CharField("任务名称", max_length=255, blank=True, default='')
    status = models.CharField(
        "任务状态", max_length=20,
        choices=Status.choices, default=Status.PENDING,
        db_index=True,
    )
    stage = models.CharField("当前阶段", max_length=20, blank=True, default='')
    progress = models.IntegerField("进度(0-100)", default=0)

    # 上传文件
    original_file = models.FileField(
        "原始文件",
        upload_to='rule_imports/%Y/%m/',
        null=True, blank=True,
    )
    file_name = models.CharField("文件名", max_length=512, blank=True, default='')
    file_size = models.BigIntegerField("文件大小(字节)", default=0)
    file_type = models.CharField("文件类型", max_length=10, blank=True, default='')

    # 输入参数 (max_pdf_pages / max_rows_per_table / chunk_size / max_tables)
    params = models.JSONField("输入参数", default=dict, blank=True)

    # 统计
    table_count = models.IntegerField("解析出的表数", default=0)
    rule_count = models.IntegerField("抽取规则数", default=0)
    imported_count = models.IntegerField("已入库规则数", default=0)

    error_detail = models.TextField("异常信息", blank=True, default='')
    celery_task_id = models.CharField("Celery任务ID", max_length=64, blank=True, default='')

    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)
    started_at = models.DateTimeField("开始执行时间", null=True, blank=True)
    finished_at = models.DateTimeField("完成时间", null=True, blank=True)

    class Meta:
        verbose_name = "规则导入任务"
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.task_name or self.file_name} ({self.get_status_display()})"


class ExtractedRule(models.Model):
    """算法抽取出的规则（暂存表）

    每条对应算法输出的一条规则，先落暂存表供人工勾选/编辑，
    再经 confirm 接口映射写入正式规则库 rules.Rule。
    """
    import_task = models.ForeignKey(
        RuleImportTask,
        on_delete=models.CASCADE,
        related_name='rules',
        verbose_name="所属任务",
    )
    seq = models.IntegerField("序号", default=0, help_text="算法内 rule_id 序号")

    rule_type = models.CharField("规则类型", max_length=40, blank=True, default='', db_index=True)
    constrained_object = models.CharField("约束对象", max_length=255, blank=True, default='')
    constraint_value = models.TextField("限制内容", blank=True, default='')
    evidence = models.JSONField("原始命中行", default=dict, blank=True)
    source = models.JSONField("来源信息", default=dict, blank=True)

    is_selected = models.BooleanField("是否勾选", default=True)
    is_imported = models.BooleanField("是否已入库", default=False)
    imported_rule_id = models.CharField(
        "关联正式规则ID", max_length=50, blank=True, default='',
        help_text="写入 rules.Rule 后的 rule_id",
    )

    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "抽取规则"
        verbose_name_plural = verbose_name
        ordering = ['import_task', 'seq']
        indexes = [
            models.Index(fields=['rule_type']),
            models.Index(fields=['import_task', 'seq']),
        ]

    def __str__(self):
        return f"[{self.rule_type}] {self.constrained_object}"
