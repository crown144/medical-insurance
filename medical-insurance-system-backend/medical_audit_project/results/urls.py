# D:\dev\medical_audit_project\results\urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ResultViewSet

# 创建一个路由器
router = DefaultRouter()

# 为 ResultViewSet 注册 URL 前缀 'results'
# 当用户访问 /api/results/ 时，将由 ResultViewSet 来处理
router.register(r'results', ResultViewSet, basename='result')

# 定义这个 App 的 URL 模式
urlpatterns = [
    path('', include(router.urls)),
]