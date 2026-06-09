from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ConfirmImportView,
    FeiJianImportBatchViewSet,
    FeiJianRawRecordViewSet,
    FeiJianStatsView,
    FileUploadView,
    PreviewImportView,
)

router = DefaultRouter()
router.register(r'feijian/import-batches', FeiJianImportBatchViewSet,
                basename='feijian-import-batch')
router.register(r'feijian/raw-records', FeiJianRawRecordViewSet,
                basename='feijian-raw-record')

urlpatterns = [
    path('', include(router.urls)),
    path('feijian/upload/', FileUploadView.as_view(), name='feijian-upload'),
    path('feijian/preview/', PreviewImportView.as_view(), name='feijian-preview'),
    path('feijian/confirm-import/', ConfirmImportView.as_view(),
         name='feijian-confirm-import'),
    path('feijian/stats/', FeiJianStatsView.as_view(), name='feijian-stats'),
]