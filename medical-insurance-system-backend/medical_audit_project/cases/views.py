# cases/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from data_adapter.medical_api import MedicalAPI
from .models import Case

class PatientCaseView(APIView):
    def get(self, request, *args, **kwargs):
        hospitalization_id = request.query_params.get('hospitalization_id')
        if not hospitalization_id:
            return Response({"error": "缺少 hospitalization_id 参数"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # 这里的逻辑和 Celery 里的 get_patient_data 一样
            case = Case.objects.get(pk=hospitalization_id)
            return Response(case.json_content)
        except Case.DoesNotExist:
            pass # 缓存未命中

        try:
            # 在生产模式下，我们假设 LOCAL_DEV_MODE=False
            source_db_config = settings.DATABASES['source_medical_db']
            pymysql_config = {k: v for k, v in source_db_config.items() if k in ['host', 'user', 'password', 'database', 'port', 'charset']}
            medical_api = MedicalAPI(db_config=pymysql_config)
            result = medical_api.get_patient_final_json_data(hospitalization_id)

            if result.get('success'):
                patient_json = result['json_data']
                Case.objects.update_or_create(
                    hospitalization_id=hospitalization_id,
                    defaults={'json_content': patient_json}
                )
                return Response(patient_json)
            else:
                return Response({"error": f"获取数据失败: {result.get('error')}"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Create your views here.
