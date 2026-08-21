from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction

from accounts.models import AccountProfile

from medical_audit_project.sso import SSOError


def resolve_local_profile(username: str) -> AccountProfile:
    user_model = get_user_model()
    with transaction.atomic():
        try:
            user = user_model.objects.select_for_update().get(username=username)
            if not user.is_active:
                raise SSOError('本系统不存在该用户或用户已停用')
        except user_model.DoesNotExist:
            user = user_model.objects.create_user(username=username)
            user.is_active = True
            user.save(update_fields=['is_active'])

        profile, _ = AccountProfile.objects.get_or_create(user=user)
        return profile
