from django.test import SimpleTestCase

from .over_standard_v2 import (
    build_charge_violation_item,
    build_medication_violation_item,
)


class ChargeViolationItemTests(SimpleTestCase):
    class RuleStub:
        match_field = "收费项目名称"
        match_value = "静脉注射"
        drug_name = "静脉注射"

    def test_uses_exact_charge_report_item_instead_of_rule_configuration(self):
        patient_json = {
            "收费报告": [
                {"收费项目名称": "静脉注射", "收费项目代码": "A001", "项目单价": "8"},
                {"收费项目名称": "静脉采血", "收费项目代码": "B002", "项目单价": "5"},
            ]
        }

        item = build_charge_violation_item(
            patient_json,
            self.RuleStub(),
            "重复收费",
            {"highlights": [{"field_path": "$.收费报告[1].收费项目名称", "highlighted_text": "静脉采血"}]},
        )

        self.assertEqual(item["收费项目名称"], "静脉采血")
        self.assertEqual(item["收费项目代码"], "B002")
        self.assertEqual(item["收费明细"][0]["收费明细索引"], 1)

    def test_does_not_fabricate_a_code_when_no_charge_item_can_be_located(self):
        item = build_charge_violation_item(
            {"收费报告": []}, self.RuleStub(), "超限定用药", {}
        )

        self.assertEqual(item["收费项目名称"], "")
        self.assertEqual(item["收费项目代码"], "")
        self.assertEqual(item["收费明细"], [])


class MedicationViolationItemTests(SimpleTestCase):
    class RuleStub:
        drug_name = "艾普拉唑"

    def test_uses_actual_medication_record_for_restricted_medication_rule(self):
        patient_json = {
            "用药信息": [
                {"药品通用名": "艾普拉唑", "药品编码": "MED-001", "剂量": "5 mg"},
                {"药品通用名": "奥美拉唑", "药品编码": "MED-002"},
            ]
        }

        item = build_medication_violation_item(
            patient_json, self.RuleStub(), "超限定用药"
        )

        self.assertEqual(item["drug_name"], "艾普拉唑")
        self.assertEqual(item["药品编码"], "MED-001")
        self.assertEqual(item["用药明细"][0]["剂量"], "5 mg")
        self.assertEqual(item["用药明细"][0]["用药明细索引"], 0)

    def test_does_not_fabricate_medication_when_no_record_matches(self):
        item = build_medication_violation_item(
            {"用药信息": []}, self.RuleStub(), "超限定用药"
        )

        self.assertEqual(item["drug_name"], "")
        self.assertEqual(item["药品通用名"], "")
        self.assertEqual(item["用药明细"], [])

# Create your tests here.
