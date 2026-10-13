import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from .models import Case
from .views import CaseListView


class CaseListViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_demo_mode_lists_only_current_mock_files(self):
        Case.objects.create(
            hospitalization_id="REMOVED-CASE",
            json_content={"患者姓名": "Cached Patient"},
        )

        with TemporaryDirectory() as temp_dir:
            mock_dir = Path(temp_dir) / "mock_patient_data"
            mock_dir.mkdir()
            (mock_dir / "CURRENT-CASE.json").write_text(
                json.dumps({"患者姓名": "Current Patient"}, ensure_ascii=False),
                encoding="utf-8",
            )

            with override_settings(DEMO_MODE=True, BASE_DIR=Path(temp_dir)):
                response = CaseListView.as_view()(self.factory.get("/api/cases/"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            [{
                "hospitalization_id": "CURRENT-CASE",
                "patient_name": "Current Patient",
            }],
        )

    @override_settings(DEMO_MODE=False)
    def test_non_demo_mode_still_lists_database_cases(self):
        Case.objects.create(
            hospitalization_id="DB-CASE",
            json_content={"患者姓名": "Database Patient"},
        )

        response = CaseListView.as_view()(self.factory.get("/api/cases/"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["hospitalization_id"], "DB-CASE")
