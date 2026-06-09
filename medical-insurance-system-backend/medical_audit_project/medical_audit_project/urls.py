from django.contrib import admin
from django.urls import path, include

from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/user/info', views.user_info, name='user_info'),
    path('api/auth/login', views.auth_login, name='auth_login'),
    path('api/menu/all', views.menu_all, name='menu_all'),
    path('api/auth/codes', views.auth_codes, name='auth_codes'),
    path('api/audit/', views.audit_detect, name='audit_detect'),
    path('api/', include('rules.urls')),
    path('api/', include('tasks.urls')),
    path('api/', include('pricings.urls')),
    path('api/', include('results.urls')),
    path('api/cases/', include('cases.urls')),
    path('api/', include('repeat_charging.urls')),
    path('api/', include('feijian.urls')),
]
