# pricings/models.py
from django.db import models

class StandardChargeItem(models.Model):
    charge_code = models.CharField("收费编码", max_length=50, primary_key=True)
    item_name = models.CharField("收费名称", max_length=255, db_index=True)
    unit = models.CharField("单位", max_length=50, null=True, blank=True)
    price_2021 = models.DecimalField("2021价格", max_digits=10, decimal_places=2, null=True, blank=True)
    price_2024 = models.DecimalField("2024价格(单价)", max_digits=10, decimal_places=2, null=True, blank=True)
    insurance_code = models.CharField("医保编码", max_length=50, null=True, blank=True, db_index=True)
    description_2021 = models.TextField("2021说明", null=True, blank=True)
    description_2024 = models.TextField("2024说明", null=True, blank=True)

    class Meta:
        verbose_name = "标准收费项目"
        verbose_name_plural = verbose_name