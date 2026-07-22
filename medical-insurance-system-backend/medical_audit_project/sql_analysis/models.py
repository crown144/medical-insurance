from django.db import models


class SQLRule(models.Model):
    rule_name = models.CharField('医保规则名称', max_length=255, unique=True, db_index=True)
    rule_type = models.CharField('规则类型', max_length=100, db_index=True)
    description = models.TextField('规则描述', blank=True)
    sql_content = models.TextField('SQL内容')
    remark = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = 'SQL规则'
        verbose_name_plural = verbose_name
        ordering = ['-updated_at', '-id']

    def __str__(self):
        return self.rule_name


class SQLExecution(models.Model):
    class ExecuteStatus(models.TextChoices):
        SUCCESS = 'success', '成功'
        FAILED = 'failed', '失败'

    sql_rule = models.ForeignKey(
        SQLRule,
        on_delete=models.CASCADE,
        related_name='executions',
        verbose_name='SQL规则',
    )
    start_date = models.DateField('开始日期')
    end_date = models.DateField('结束日期')
    execute_status = models.CharField(
        '执行状态',
        max_length=20,
        choices=ExecuteStatus.choices,
        default=ExecuteStatus.SUCCESS,
        db_index=True,
    )
    execute_time = models.DateTimeField('执行时间')
    duration = models.PositiveIntegerField('执行耗时(毫秒)', default=0)
    row_count = models.PositiveIntegerField('返回记录数', default=0)
    result_json = models.JSONField('结果JSON', default=dict, blank=True)
    error_message = models.TextField('错误信息', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = 'SQL执行记录'
        verbose_name_plural = verbose_name
        ordering = ['-execute_time', '-id']

    def __str__(self):
        return f'{self.sql_rule.rule_name} ({self.start_date}~{self.end_date})'

