# tasks/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TaskViewSet
from .inhos_views import InhosNumbersAPIView

router = DefaultRouter()
router.register(r'tasks', TaskViewSet, basename='task')

urlpatterns = [
    path('', include(router.urls)),
    path('inhos-numbers/', InhosNumbersAPIView.as_view(), name='inhos-numbers'),
]