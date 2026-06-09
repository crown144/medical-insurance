from django.db import models


class FeiJianImportBatch(models.Model):
    """飞检导入批次"""
    class Status(models.TextChoices):
        UPLOADING = 'uploading', '上传中'
        ANALYZING = 'analyzing', '分析中'
        MAPPING = 'mapping', '待确认映射'
        IMPORTING = 'importing', '导入中'
        SUCCESS = 'success', '导入成功'
        FAILED = 'failed', '导入失败'

    file_name = models.CharField("文件名", max_length=512)
    file_size = models.BigIntegerField("文件大小(字节)", default=0)
    original_file = models.FileField(
        "原始文件",
        upload_to='feijian_imports/%Y/%m/',
        null=True, blank=True,
    )
    status = models.CharField(
        "状态", max_length=20,
        choices=Status.choices, default=Status.UPLOADING,
        db_index=True,
    )
    record_count = models.IntegerField("记录总数", default=0)
    success_count = models.IntegerField("成功导入数", default=0)
    error_count = models.IntegerField("失败数", default=0)
    error_detail = models.TextField("错误详情", blank=True, default='')

    # 列映射结果 (JSON)
    # 格式: {"住院号": "column_A", "问题类型": "column_C", ...}
    detected_columns = models.JSONField("检测到的列名", default=list, blank=True)
    column_mapping = models.JSONField("列映射关系", default=dict, blank=True)
    # 格式: {"hospitalization_no": {"column": "A", "confidence": 0.95, "method": "regex"}, ...}
    sample_rows = models.JSONField("样本数据(前5行)", default=list, blank=True)

    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "飞检导入批次"
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.file_name} ({self.get_status_display()})"


class FeiJianRawRecord(models.Model):
    """飞检原始记录"""
    import_batch = models.ForeignKey(
        FeiJianImportBatch,
        on_delete=models.CASCADE,
        related_name='records',
        verbose_name="导入批次",
    )
    row_index = models.IntegerField("行号", default=0)

    # 识别出的关键字段
    hospitalization_no = models.CharField("住院号", max_length=64, db_index=True)
    patient_name = models.CharField("患者姓名", max_length=128, blank=True, default='')
    hospital_name = models.CharField("医疗机构", max_length=256, blank=True, default='')
    admission_date = models.CharField("入院日期", max_length=32, blank=True, default='')
    discharge_date = models.CharField("出院日期", max_length=32, blank=True, default='')
    issue_category = models.CharField("问题类别", max_length=256, blank=True, default='')
    issue_description = models.TextField("问题描述", blank=True, default='')
    involved_amount = models.DecimalField(
        "涉及金额", max_digits=14, decimal_places=2, default=0,
    )
    audit_org = models.CharField("飞检机构", max_length=256, blank=True, default='')
    audit_date = models.CharField("飞检日期", max_length=32, blank=True, default='')

    # 完整原始数据 (保留所有列)
    raw_data = models.JSONField("原始行数据", default=dict, blank=True)

    # 关联后续审查
    audit_task_id = models.CharField("关联审查任务ID", max_length=64, blank=True, default='')

    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "飞检原始记录"
        verbose_name_plural = verbose_name
        ordering = ['import_batch', 'row_index']
        indexes = [
            models.Index(fields=['hospitalization_no']),
            models.Index(fields=['import_batch', 'row_index']),
        ]

    def __str__(self):
        return f"{self.hospitalization_no} - {self.issue_category or '未分类'}"