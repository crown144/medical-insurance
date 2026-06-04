# apps/rules/models.py

from django.db import models

class MedicalCode(models.Model):
    """医保药品代码表"""
    code = models.CharField("药品代码", max_length=100, primary_key=True)
    name = models.CharField("国家医保药品名称", max_length=255, db_index=True)

    class Meta:
        verbose_name = "医保药品代码"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.name} ({self.code})"


class Rule(models.Model):
    # 核心字段调整
    rule_id = models.CharField("规则号", max_length=50, unique=True, help_text="业务规则ID，如 rule_001")
    drug_name = models.CharField("药品名称", max_length=255, db_index=True, blank=True, help_text="药品名称或收费项目名称，用于匹配")
    description = models.TextField("规则描述")
    logic_expression = models.TextField("逻辑表达式", blank=True, help_text="旧版逻辑表达式（已弃用，保留用于兼容）")
    rule_code = models.TextField("规则代码", blank=True, help_text="Python函数代码字符串，定义 execute_rule(medical_record, current_item) 函数")
    status = models.BooleanField("是否启用", default=True) # 之前叫 status，现在明确为布尔值
     
    type = models.CharField("规则类型", max_length=50, db_index=True, blank=True, default="超限定用药") # 加上这个字段
    # 匹配字段：用于根据收费项目匹配规则
    match_field = models.CharField("匹配字段", max_length=50, blank=True, help_text="用于匹配的字段名，如 '收费项目名称' 或 '收费项目代码'")
    match_value = models.CharField("匹配值", max_length=255, blank=True, db_index=True, help_text="匹配字段的值，如药品名称或代码")
    # 保留审计字段
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "审核规则"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.rule_id} - {self.drug_name}"
    
class AuditTemplate(models.Model):
    """审核模板表"""
    template_id = models.CharField("模板ID", max_length=100, primary_key=True)
    description = models.CharField("模板描述", max_length=255)
    template_json = models.JSONField("模板JSON结构")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "审核模板"
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.description
class BusinessFunction(models.Model):
    func_name = models.CharField("函数名称", max_length=100, unique=True, db_index=True, help_text="例如 is_acute_stroke")
    description = models.TextField("函数描述", blank=True, help_text="LLM生成的函数说明")
    function_body = models.TextField("函数代码", help_text="完整的 Python 函数定义代码")
    
    # 版本控制或来源标记
    version = models.IntegerField("版本号", default=1)
    is_active = models.BooleanField("是否启用", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "业务函数"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.func_name} (v{self.version})"