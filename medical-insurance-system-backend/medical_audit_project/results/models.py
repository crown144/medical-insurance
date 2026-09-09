from django.db import models
# 注意外键引用的变化
from tasks.models import Task
from rules.models import Rule

class Result(models.Model):
    """审核结果表（记录违规项）"""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='results', verbose_name="所属任务")
    rule = models.ForeignKey(Rule, on_delete=models.PROTECT, verbose_name="命中规则")
    hospitalization_id = models.CharField("住院流水号", max_length=100, db_index=True)
    violation_item = models.TextField("违规项目快照", help_text="例如，违规药品的JSON快照", null=True, blank=True)
    reason = models.TextField("违规原因", null=True, blank=True)
    created_at = models.DateTimeField("生成时间", auto_now_add=True)  
    # --- 新增下面这一行 ---
    discharge_date = models.DateTimeField("出院日期", null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = "违规结果"
        verbose_name_plural = verbose_name


class Highlight(models.Model):
    """结果高亮信息表"""
    result = models.ForeignKey(Result, on_delete=models.CASCADE, related_name='highlights', verbose_name="所属结果")
    field_path = models.CharField("高亮字段路径", max_length=255, help_text="违规字段的JSONPath")
    highlighted_text = models.TextField("高亮文本内容")

    class Meta:
        verbose_name = "高亮信息"
        verbose_name_plural = verbose_name
