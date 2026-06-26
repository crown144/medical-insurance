# cases/views.py
import json
import os
from pathlib import Path

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from data_adapter.medical_api import MedicalAPI
from data_adapter.source_db import get_source_db_config

from .models import Case


def extract_patient_name(patient_json):
    if not isinstance(patient_json, dict):
        return ""

    candidate_keys = {"姓名", "患者姓名", "病人姓名", "名字", "患者名称"}

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in candidate_keys and isinstance(item, str):
                    return item.strip()
                found = walk(item)
                if found:
                    return found
        elif isinstance(value, list):
            for item in value:
                found = walk(item)
                if found:
                    return found
        return ""

    return walk(patient_json)


class CaseListView(APIView):
    def get(self, request, *args, **kwargs):
        items = []
        seen_ids = set()

        for case in Case.objects.all().order_by('hospitalization_id'):
            items.append({
                "hospitalization_id": case.hospitalization_id,
                "patient_name": extract_patient_name(case.json_content),
            })
            seen_ids.add(case.hospitalization_id)

        if getattr(settings, 'DEMO_MODE', False):
            mock_dir = Path(settings.BASE_DIR) / 'mock_patient_data'
            if mock_dir.exists():
                for json_file in sorted(mock_dir.glob('*.json')):
                    hospitalization_id = json_file.stem
                    if hospitalization_id in seen_ids:
                        continue
                    patient_name = ""
                    try:
                        patient_name = extract_patient_name(
                            json.loads(json_file.read_text(encoding='utf-8'))
                        )
                    except Exception:
                        patient_name = ""
                    items.append({
                        "hospitalization_id": hospitalization_id,
                        "patient_name": patient_name,
                    })

        return Response(items)

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
            if getattr(settings, 'DEMO_MODE', False):
                demo_path = os.path.join(settings.BASE_DIR, 'mock_patient_data', f'{hospitalization_id}.json')
                if os.path.exists(demo_path):
                    with open(demo_path, 'r', encoding='utf-8') as f:
                        patient_json = json.load(f)
                    Case.objects.update_or_create(
                        hospitalization_id=hospitalization_id,
                        defaults={'json_content': patient_json}
                    )
                    return Response(patient_json)
                return Response({"error": "Demo环境未找到病例数据"}, status=status.HTTP_404_NOT_FOUND)

            medical_api = MedicalAPI(db_config=get_source_db_config())
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
