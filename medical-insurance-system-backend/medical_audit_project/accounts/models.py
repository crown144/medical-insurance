from django.conf import settings
from django.db import models


class AccountProfile(models.Model):
    class Role(models.TextChoices):
        NORMAL = 'normal', '普通用户'
        DEVELOPER = 'developer', '开发用户'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='audit_profile',
        verbose_name='用户',
    )
    role = models.CharField('系统角色', max_length=20, choices=Role.choices, default=Role.NORMAL, db_index=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '审核账号角色'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.user.username} ({self.get_role_display()})'
