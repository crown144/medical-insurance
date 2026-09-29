from django.urls import path

from .views import PortalActionView


urlpatterns = [
    path('actions/app-admin-set', PortalActionView.as_view(action_type='app_admin_set'), name='portal-app-admin-set'),
    path('actions/query-user-status', PortalActionView.as_view(action_type='query_user_status'), name='portal-query-user-status'),
    path('actions/remove-user', PortalActionView.as_view(action_type='remove_user'), name='portal-remove-user'),
    path('actions/disable-user', PortalActionView.as_view(action_type='disable_user'), name='portal-disable-user'),
    path('actions/enable-user', PortalActionView.as_view(action_type='enable_user'), name='portal-enable-user'),
    path('actions/default-role', PortalActionView.as_view(action_type='default_role_callback'), name='portal-default-role'),
]
