from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PortalUserBinding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('portal_user_id', models.CharField(max_length=128, unique=True, verbose_name='门户用户 ID')),
                ('access_status', models.CharField(choices=[('ENABLED', '已启用'), ('DISABLED', '已停用'), ('REMOVED', '已移除')], db_index=True, default='ENABLED', max_length=16, verbose_name='应用访问状态')),
                ('is_admin', models.BooleanField(default=False, verbose_name='是否应用管理员')),
                ('previous_role', models.CharField(blank=True, default='', max_length=20, verbose_name='变更前角色')),
                ('portal_expired_at', models.BigIntegerField(blank=True, null=True, verbose_name='门户过期时间')),
                ('profile_data', models.JSONField(blank=True, default=dict, verbose_name='门户用户扩展资料')),
                ('last_synced_at', models.DateTimeField(blank=True, null=True, verbose_name='最近同步时间')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='portal_binding', to=settings.AUTH_USER_MODEL, verbose_name='本地用户')),
            ],
            options={
                'verbose_name': '门户用户绑定',
                'verbose_name_plural': '门户用户绑定',
            },
        ),
        migrations.CreateModel(
            name='PortalActionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action_type', models.CharField(db_index=True, max_length=64, verbose_name='动作类型')),
                ('portal_user_id', models.CharField(blank=True, db_index=True, max_length=128, verbose_name='门户用户 ID')),
                ('request_fingerprint', models.CharField(db_index=True, max_length=64, verbose_name='请求指纹')),
                ('before_state', models.JSONField(blank=True, null=True, verbose_name='变更前状态')),
                ('after_state', models.JSONField(blank=True, null=True, verbose_name='变更后状态')),
                ('result_code', models.IntegerField(default=0, verbose_name='结果码')),
                ('trace_id', models.CharField(db_index=True, max_length=64, verbose_name='追踪 ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='执行时间')),
            ],
            options={
                'verbose_name': '门户动作审计',
                'verbose_name_plural': '门户动作审计',
                'ordering': ('-created_at',),
            },
        ),
        migrations.AddIndex(
            model_name='portaluserbinding',
            index=models.Index(fields=['portal_user_id', 'access_status'], name='portal_inte_portal__9b19ab_idx'),
        ),
    ]
