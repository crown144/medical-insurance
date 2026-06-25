# apps/tasks/models.py

from django.db import models

from rules.models import Rule


class Task(models.Model):
    """审核任务表"""

    class Status(models.TextChoices):
        PENDING = 'pending', '待处理'
        RUNNING = 'running', '处理中'
        COMPLETED = 'completed', '已完成'
        FAILED = 'failed', '失败'

    name = models.CharField("任务名称", max_length=255)
    status = models.CharField("任务状态", max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    rules = models.ManyToManyField(Rule, verbose_name="关联规则", through='TaskRule')
    hospitalization_ids = models.JSONField("待审核住院号列表")
    mdc_org_cd = models.CharField("医疗机构代码", max_length=50, blank=True, default='')
    summary = models.TextField("任务摘要/报告", blank=True, null=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    started_at = models.DateTimeField("开始时间", null=True, blank=True)
    completed_at = models.DateTimeField("完成时间", null=True, blank=True)
    selected_schemas = models.JSONField("选择的检测方案", default=list, blank=True)
    repeat_charging_child_codes = models.JSONField("重复收费选择的子规则医保编码", default=list, blank=True)
    repeat_charging_pairs = models.JSONField("重复收费选择的父-子医保编码对", default=list, blank=True)

    class Meta:
        verbose_name = "审核任务"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"任务: {self.name} ({self.get_status_display()})"


class TaskRule(models.Model):
    """任务与规则的中间表"""

    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    rule = models.ForeignKey(Rule, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('task', 'rule')
