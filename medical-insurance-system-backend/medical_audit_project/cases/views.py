# cases/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from data_adapter.medical_api import MedicalAPI
from data_adapter.source_db import get_source_db_config
from .models import Case
from tasks.models import Task

class PatientCaseView(APIView):
    def get(self, request, *args, **kwargs):
        hospitalization_id = request.query_params.get('hospitalization_id')
        if not hospitalization_id:
            return Response({"error": "缺少 hospitalization_id 参数"}, status=status.HTTP_400_BAD_REQUEST)

        task_id = request.query_params.get('task_id')
        mdc_org_cd = (request.query_params.get('mdc_org_cd') or '').strip()
        if task_id and not mdc_org_cd:
            try:
                task = Task.objects.only('mdc_org_cd').get(pk=task_id)
                mdc_org_cd = (task.mdc_org_cd or '').strip()
            except (Task.DoesNotExist, ValueError):
                pass

        cache_keys = [f'{mdc_org_cd}:{hospitalization_id}'] if mdc_org_cd else [hospitalization_id]

        # 这里的逻辑和 Celery 里的 get_patient_data 保持一致：
        # 优先使用带机构代码的缓存，避免同住院号跨机构或旧缓存污染详情页。
        for cache_key in cache_keys:
            try:
                case = Case.objects.get(pk=cache_key)
                return Response(case.json_content)
            except Case.DoesNotExist:
                pass # 缓存未命中

        try:
            # 在生产模式下，我们假设 LOCAL_DEV_MODE=False
            medical_api = MedicalAPI(db_config=get_source_db_config())
            result = medical_api.get_patient_final_json_data(hospitalization_id, mdc_org_cd or None)

            if result.get('success'):
                patient_json = result['json_data']
                Case.objects.update_or_create(
                    hospitalization_id=cache_keys[0],
                    defaults={'json_content': patient_json}
                )
                return Response(patient_json)
            else:
                return Response({"error": f"获取数据失败: {result.get('error')}"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Create your views here.
