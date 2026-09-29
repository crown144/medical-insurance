from django.contrib import admin

from .models import PortalActionLog, PortalUserBinding


@admin.register(PortalUserBinding)
class PortalUserBindingAdmin(admin.ModelAdmin):
    list_display = ('portal_user_id', 'user', 'access_status', 'is_admin', 'portal_expired_at', 'updated_at')
    list_filter = ('access_status', 'is_admin')
    search_fields = ('portal_user_id', 'user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at', 'last_synced_at')


@admin.register(PortalActionLog)
class PortalActionLogAdmin(admin.ModelAdmin):
    list_display = ('action_type', 'portal_user_id', 'result_code', 'trace_id', 'created_at')
    list_filter = ('action_type', 'result_code')
    search_fields = ('portal_user_id', 'trace_id', 'request_fingerprint')
    readonly_fields = [field.name for field in PortalActionLog._meta.fields]
