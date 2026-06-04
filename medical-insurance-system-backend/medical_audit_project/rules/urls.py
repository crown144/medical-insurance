# rules/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RuleViewSet

# 创建一个路由器
router = DefaultRouter()
# 为视图集注册 URL 前缀 'rules'
router.register(r'rules', RuleViewSet, basename='rule')

# 关键在这里！确保这个变量的名字是 urlpatterns，而且是个列表！
urlpatterns = [
    path('', include(router.urls)),
]