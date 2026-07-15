from django.test import SimpleTestCase

from .over_standard_v2 import build_charge_violation_item


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

# Create your tests here.
