import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.models import AccountProfile


class Command(BaseCommand):
    help = '创建缺失的普通用户和开发用户；已存在的账号不会被覆盖。'

    ACCOUNTS = (
        ('normal', AccountProfile.Role.NORMAL, 'MEDICAL_AUDIT_NORMAL_USERNAME', 'MEDICAL_AUDIT_NORMAL_PASSWORD'),
        ('developer', AccountProfile.Role.DEVELOPER, 'MEDICAL_AUDIT_DEVELOPER_USERNAME', 'MEDICAL_AUDIT_DEVELOPER_PASSWORD'),
    )

    def handle(self, *args, **options):
        user_model = get_user_model()
        for default_username, role, username_env, password_env in self.ACCOUNTS:
            username = os.environ.get(username_env, default_username).strip()
            password = os.environ.get(password_env, '123456')
            user, created = user_model.objects.get_or_create(username=username)
            if created:
                user.set_password(password)
                user.save(update_fields=['password'])
                self.stdout.write(self.style.SUCCESS(f'已创建 {role} 用户：{username}'))
            profile, profile_created = AccountProfile.objects.get_or_create(user=user, defaults={'role': role})
            if not profile_created and profile.role != role:
                profile.role = role
                profile.save(update_fields=['role', 'updated_at'])
            if not created:
                self.stdout.write(f'保留已有 {role} 用户：{username}')
