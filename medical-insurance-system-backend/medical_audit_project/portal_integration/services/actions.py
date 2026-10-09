import hashlib
import json
import time

from django.db import transaction

from accounts.models import AccountProfile
from portal_integration.models import PortalActionLog, PortalUserBinding

from .user_sync import PortalUserSyncService


def is_binding_expired(binding, *, now=None):
    value = binding.portal_expired_at
    if value in (None, -1):
        return False
    timestamp = value / 1000 if value > 100_000_000_000 else value
    return timestamp <= (now if now is not None else time.time())


def _snapshot(binding):
    if not binding:
        return None
    profile = AccountProfile.objects.filter(user=binding.user).first()
    return {
        'access_status': binding.access_status,
        'is_admin': binding.is_admin,
        'role': profile.role if profile else None,
        'is_active': binding.user.is_active,
        'portal_expired_at': binding.portal_expired_at,
    }


def _fingerprint(action_type, payload):
    raw = json.dumps(
        {'action': action_type, 'payload': payload},
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    ).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def record_action_log(
    action_type,
    portal_user_id,
    payload,
    *,
    trace_id,
    result_code,
    before=None,
    after=None,
):
    PortalActionLog.objects.create(
        action_type=action_type,
        portal_user_id=portal_user_id,
        request_fingerprint=_fingerprint(action_type, payload),
        before_state=before,
        after_state=after,
        result_code=result_code,
        trace_id=trace_id,
    )


def _audit(action_type, portal_user_id, payload, before, after, trace_id):
    record_action_log(
        action_type,
        portal_user_id,
        payload,
        trace_id=trace_id,
        result_code=0,
        before=before,
        after=after,
    )


class PortalActionService:
    def __init__(self, *, sync_service=None):
        self.sync_service = sync_service or PortalUserSyncService()

    def _ensure(self, portal_user_id):
        self.sync_service.ensure_binding(portal_user_id)

    def sync_user(self, detail, *, action_type, trace_id):
        portal_user_id = detail['id']
        with transaction.atomic():
            before = _snapshot(self._locked_optional_binding(portal_user_id))
            binding = self.sync_service.sync_detail(detail, expected_id=portal_user_id)
            _audit(action_type, portal_user_id, detail, before, _snapshot(binding), trace_id)

    def _locked_binding(self, portal_user_id):
        return PortalUserBinding.objects.select_for_update().select_related('user').get(
            portal_user_id=portal_user_id,
        )

    def _locked_optional_binding(self, portal_user_id):
        return PortalUserBinding.objects.select_for_update().select_related('user').filter(
            portal_user_id=portal_user_id,
        ).first()

    def set_app_admin(self, portal_user_id, *, trace_id):
        with transaction.atomic():
            self._ensure(portal_user_id)
            binding = self._locked_binding(portal_user_id)
            before = _snapshot(binding)
            profile, _ = AccountProfile.objects.select_for_update().get_or_create(user=binding.user)
            if profile.role != AccountProfile.Role.ADMIN:
                profile.role = AccountProfile.Role.ADMIN
                profile.save(update_fields=['role', 'updated_at'])
            binding.previous_role = ''
            binding.is_admin = True
            binding.access_status = PortalUserBinding.AccessStatus.ENABLED
            binding.user.is_active = binding.profile_data.get('status') != 2
            binding.user.save(update_fields=['is_active'])
            binding.save(update_fields=['previous_role', 'is_admin', 'access_status', 'updated_at'])
            after = _snapshot(binding)
            _audit('app_admin_set', portal_user_id, {'user_id': portal_user_id}, before, after, trace_id)

    def remove_user(self, portal_user_id, *, trace_id):
        with transaction.atomic():
            binding = self._locked_optional_binding(portal_user_id)
            before = _snapshot(binding)
            if binding:
                profile = AccountProfile.objects.select_for_update().filter(user=binding.user).first()
                if profile:
                    binding.previous_role = profile.role
                binding.access_status = PortalUserBinding.AccessStatus.REMOVED
                binding.is_admin = False
                binding.user.is_active = False
                binding.user.save(update_fields=['is_active'])
                binding.save(update_fields=['previous_role', 'access_status', 'is_admin', 'updated_at'])
            after = _snapshot(binding)
            _audit('remove_user', portal_user_id, {'user_id': portal_user_id}, before, after, trace_id)

    def disable_user(self, portal_user_id, *, trace_id):
        with transaction.atomic():
            binding = self._locked_optional_binding(portal_user_id)
            before = _snapshot(binding)
            if binding:
                profile = AccountProfile.objects.select_for_update().filter(user=binding.user).first()
                if profile:
                    binding.previous_role = profile.role
                binding.access_status = PortalUserBinding.AccessStatus.DISABLED
                binding.user.is_active = False
                binding.user.save(update_fields=['is_active'])
                binding.save(update_fields=['previous_role', 'access_status', 'updated_at'])
            after = _snapshot(binding)
            _audit('disable_user', portal_user_id, {'user_id': portal_user_id}, before, after, trace_id)

    def enable_user(self, portal_user_id, *, trace_id):
        with transaction.atomic():
            self._ensure(portal_user_id)
            binding = self._locked_binding(portal_user_id)
            before = _snapshot(binding)
            profile, _ = AccountProfile.objects.select_for_update().get_or_create(user=binding.user)
            if (
                binding.access_status != PortalUserBinding.AccessStatus.ENABLED
                and binding.previous_role in AccountProfile.Role.values
            ):
                profile.role = binding.previous_role
                profile.save(update_fields=['role', 'updated_at'])
            binding.is_admin = profile.role == AccountProfile.Role.ADMIN
            binding.previous_role = ''
            binding.access_status = PortalUserBinding.AccessStatus.ENABLED
            binding.user.is_active = binding.profile_data.get('status') != 2
            binding.user.save(update_fields=['is_active'])
            binding.save(update_fields=['previous_role', 'is_admin', 'access_status', 'updated_at'])
            after = _snapshot(binding)
            _audit('enable_user', portal_user_id, {'user_id': portal_user_id}, before, after, trace_id)

    def set_default_role(self, portal_user_id, *, trace_id):
        with transaction.atomic():
            self._ensure(portal_user_id)
            binding = self._locked_binding(portal_user_id)
            before = _snapshot(binding)
            profile, _ = AccountProfile.objects.select_for_update().get_or_create(user=binding.user)
            if profile.role != AccountProfile.Role.DEVELOPER:
                profile.role = AccountProfile.Role.NORMAL
                profile.save(update_fields=['role', 'updated_at'])
            binding.previous_role = ''
            binding.is_admin = False
            binding.access_status = PortalUserBinding.AccessStatus.ENABLED
            binding.user.is_active = binding.profile_data.get('status') != 2
            binding.user.save(update_fields=['is_active'])
            binding.save(update_fields=['previous_role', 'is_admin', 'access_status', 'updated_at'])
            after = _snapshot(binding)
            _audit('default_role_callback', portal_user_id, {'user_id': portal_user_id}, before, after, trace_id)

    def query_user_status(self, portal_user_ids):
        bindings = {
            item.portal_user_id: item
            for item in PortalUserBinding.objects.select_related('user').filter(
                portal_user_id__in=set(portal_user_ids),
            )
        }
        result = []
        for portal_user_id in portal_user_ids:
            binding = bindings.get(portal_user_id)
            if not binding:
                result.append({
                    'user_id': portal_user_id,
                    'status': 0,
                    'admin': False,
                    'expired': False,
                    'exists': 0,
                })
                continue

            removed = binding.access_status == PortalUserBinding.AccessStatus.REMOVED
            expired = is_binding_expired(binding)
            enabled = (
                binding.access_status == PortalUserBinding.AccessStatus.ENABLED
                and binding.user.is_active
                and binding.profile_data.get('status') != 2
                and not expired
            )
            result.append({
                'user_id': portal_user_id,
                'status': 1 if enabled else 0,
                'admin': False if removed else binding.is_admin,
                'expired': expired,
                'exists': 0 if removed else 1,
            })
        return result
