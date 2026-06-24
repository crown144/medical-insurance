# rule_import/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import RuleImportTaskViewSet, RuleImportUploadView

router = DefaultRouter()
router.register(r'rule-import/tasks', RuleImportTaskViewSet,
                basename='rule-import-task')

urlpatterns = [
    path('', include(router.urls)),
    path('rule-import/upload/', RuleImportUploadView.as_view(),
         name='rule-import-upload'),
]
