from django.conf import settings
from django.db import models


class PortalUserBinding(models.Model):
    class AccessStatus(models.TextChoices):
        ENABLED = 'ENABLED', '已启用'
        DISABLED = 'DISABLED', '已停用'
        REMOVED = 'REMOVED', '已移除'

    portal_user_id = models.CharField('门户用户 ID', max_length=128, unique=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='portal_binding',
        verbose_name='本地用户',
    )
    access_status = models.CharField(
        '应用访问状态',
        max_length=16,
        choices=AccessStatus.choices,
        default=AccessStatus.ENABLED,
        db_index=True,
    )
    is_admin = models.BooleanField('是否应用管理员', default=False)
    previous_role = models.CharField('变更前角色', max_length=20, blank=True, default='')
    portal_expired_at = models.BigIntegerField('门户过期时间', null=True, blank=True)
    profile_data = models.JSONField('门户用户扩展资料', default=dict, blank=True)
    last_synced_at = models.DateTimeField('最近同步时间', null=True, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '门户用户绑定'
        verbose_name_plural = verbose_name
        indexes = [models.Index(fields=['portal_user_id', 'access_status'])]

    def __str__(self):
        return f'{self.portal_user_id} -> {self.user_id}'


class PortalActionLog(models.Model):
    action_type = models.CharField('动作类型', max_length=64, db_index=True)
    portal_user_id = models.CharField('门户用户 ID', max_length=128, blank=True, db_index=True)
    request_fingerprint = models.CharField('请求指纹', max_length=64, db_index=True)
    before_state = models.JSONField('变更前状态', null=True, blank=True)
    after_state = models.JSONField('变更后状态', null=True, blank=True)
    result_code = models.IntegerField('结果码', default=0)
    trace_id = models.CharField('追踪 ID', max_length=64, db_index=True)
    created_at = models.DateTimeField('执行时间', auto_now_add=True)

    class Meta:
        verbose_name = '门户动作审计'
        verbose_name_plural = verbose_name
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.action_type}:{self.portal_user_id}:{self.result_code}'
