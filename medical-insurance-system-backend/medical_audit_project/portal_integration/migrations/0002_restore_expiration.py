from django.db import migrations


def restore_expiration(apps, schema_editor):
    """Recover timestamps dropped by the original user-sync parser."""
    Binding = apps.get_model('portal_integration', 'PortalUserBinding')
    bindings = Binding.objects.filter(portal_expired_at__isnull=True)
    for binding in bindings.iterator():
        detail = binding.profile_data
        if not isinstance(detail, dict):
            raise RuntimeError(f'门户用户绑定 {binding.pk} 的历史资料格式无效，请修正后重新迁移。')
        value = next((detail[key] for key in ('expired', 'expired_at', 'expire_time', 'expiration_time')
                      if detail.get(key) not in (None, '')), None)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise RuntimeError(f'门户用户绑定 {binding.pk} 的历史过期时间格式无效，请修正后重新迁移。')
        try:
            timestamp = int(value)
        except ValueError as exc:
            raise RuntimeError(f'门户用户绑定 {binding.pk} 的历史过期时间格式无效，请修正后重新迁移。') from exc
        if not -1 <= timestamp <= 2 ** 63 - 1:
            raise RuntimeError(f'门户用户绑定 {binding.pk} 的历史过期时间超出范围，请修正后重新迁移。')
        Binding.objects.filter(pk=binding.pk, portal_expired_at__isnull=True).update(portal_expired_at=timestamp)


class Migration(migrations.Migration):
    dependencies = [('portal_integration', '0001_initial')]
    operations = [migrations.RunPython(restore_expiration, migrations.RunPython.noop)]
