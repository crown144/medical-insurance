from django.db import models


class ParentChildRelation(models.Model):
    """
    父子项目编码映射表
    来源于1016_type1的father-child.csv，支持医保统一编码与收费编码两套编码。
    """

    parent_insurance_code = models.CharField(max_length=255, blank=True, null=True, verbose_name="父项目医保统一编码")
    parent_charge_code = models.CharField(max_length=64, db_index=True, verbose_name="父项目收费编码")
    parent_name = models.CharField(max_length=255, verbose_name="父项目名称")

    child_insurance_code = models.CharField(max_length=255, blank=True, null=True, verbose_name="子项目医保统一编码")
    child_charge_code = models.CharField(max_length=64, db_index=True, verbose_name="子项目收费编码")
    child_name = models.CharField(max_length=255, verbose_name="子项目名称")
    child_order = models.IntegerField(default=0, verbose_name="子项目顺序")

    class Meta:
        verbose_name = "父子项目映射"
        verbose_name_plural = "父子项目映射"
        indexes = [
            models.Index(fields=["parent_charge_code", "child_charge_code"], name="idx_parent_child_code"),
            models.Index(fields=["parent_charge_code", "child_order"], name="idx_parent_child_order"),
        ]
        ordering = ["parent_charge_code", "child_order", "id"]

    def __str__(self):
        return f"{self.parent_name}({self.parent_charge_code}) -> {self.child_name}({self.child_charge_code})"