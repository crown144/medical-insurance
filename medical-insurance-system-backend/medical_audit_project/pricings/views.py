from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import StandardChargeItem
from .serializers import StandardChargeItemSerializer

class StandardChargeItemViewSet(viewsets.ModelViewSet):
    """
    提供 StandardChargeItem 资源的 CRUD (创建、读取、更新、删除) API 接口。
    """
    # 1. 查询集：定义这个视图集要操作的数据范围
    queryset = StandardChargeItem.objects.all().order_by('charge_code')

    # 2. 序列化器类：指定用于序列化/反序列化的类
    serializer_class = StandardChargeItemSerializer

    # 3. 过滤、搜索和排序功能 (与您 tasks app 的风格保持一致)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    # a. 精确过滤：允许通过字段进行精确或范围查询
    #    例如: /api/pricings/standard-charge-items/?charge_code=...&insurance_code=...
    filterset_fields = ['charge_code', 'insurance_code']
    
    # b. 模糊搜索：允许对指定字段进行全文搜索
    #    例如: /api/pricings/standard-charge-items/?search=阿司匹林
    search_fields = ['item_name', 'description_2024']

    # c. 排序：允许客户端指定排序字段
    #    例如: /api/pricings/standard-charge-items/?ordering=-price_2024 (按价格降序)
    ordering_fields = ['charge_code', 'item_name', 'price_2024']