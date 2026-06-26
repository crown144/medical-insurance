# cases/urls.py
from django.urls import path

from .views import CaseListView, PatientCaseView

urlpatterns = [
    path('', CaseListView.as_view(), name='case-list'),
    path('patient-case/', PatientCaseView.as_view(), name='patient-case'),
]
