from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ParentChildRelationViewSet

router = DefaultRouter()
router.register(r'repeat-charging/father-child', ParentChildRelationViewSet, basename='father-child')

urlpatterns = [
    path('', include(router.urls)),
]