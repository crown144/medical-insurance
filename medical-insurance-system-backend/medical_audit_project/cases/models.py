# cases/models.py
from django.db import models

class Case(models.Model):
    hospitalization_id = models.CharField("住院流水号", max_length=100, primary_key=True)
    json_content = models.JSONField("病历JSON内容")
    last_updated = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "缓存病历"
        verbose_name_plural = verbose_name