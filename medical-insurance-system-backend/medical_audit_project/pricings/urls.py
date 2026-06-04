from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views  # 假设你的视图函数/视图集在 views.py 中

# 1. 创建一个路由器实例
router = DefaultRouter()

# 2. 注册你的视图集
#    'standard-charge-items' 是这个API资源的基础URL
#    views.StandardChargeItemViewSet 是处理这个资源请求的视图集
#    basename='standardchargeitem' 是URL名称的前缀
router.register(r'standard-charge-items', views.StandardChargeItemViewSet, basename='standardchargeitem')

# 3. urlpatterns 会自动包含由路由器生成的所有URL
urlpatterns = [
    path('', include(router.urls)),
]