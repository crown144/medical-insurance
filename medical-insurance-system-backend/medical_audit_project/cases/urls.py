# cases/urls.py
from django.urls import path
from .views import PatientCaseView

urlpatterns = [
    path('patient-case/', PatientCaseView.as_view(), name='patient-case'),
]