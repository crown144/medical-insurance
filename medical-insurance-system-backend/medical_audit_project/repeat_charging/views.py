from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import ParentChildRelation
from .serializers import ParentChildRelationSerializer


class ParentChildRelationViewSet(ReadOnlyModelViewSet):
    queryset = ParentChildRelation.objects.all().order_by('parent_charge_code', 'child_order', 'id')
    serializer_class = ParentChildRelationSerializer
    permission_classes = [AllowAny]
    pagination_class = None  # 返回完整列表，方便前端一次性加载
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['parent_charge_code', 'child_charge_code']
    search_fields = ['parent_name', 'child_name', 'parent_insurance_code', 'child_insurance_code']
    ordering_fields = ['parent_charge_code', 'child_charge_code']