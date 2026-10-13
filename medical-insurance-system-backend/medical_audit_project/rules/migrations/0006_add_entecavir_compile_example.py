from django.db import migrations


RULE_ID = "rule_131"
RULE_DESCRIPTION = (
    "限慢性乙型肝炎成人患者或2岁至<18岁慢性HBV感染代偿性肝病的"
    "核苷初治儿童患者。"
)


def add_entecavir_compile_example(apps, schema_editor):
    Rule = apps.get_model("rules", "Rule")
    rule, created = Rule.objects.get_or_create(
        rule_id=RULE_ID,
        defaults={
            "drug_name": "恩替卡韦口服溶液",
            "description": RULE_DESCRIPTION,
            "logic_expression": "",
            "rule_code": "",
            "status": True,
            "type": "超限定用药",
            "match_field": "",
            "match_value": "",
        },
    )
    if not created:
        rule.drug_name = "恩替卡韦口服溶液"
        rule.description = RULE_DESCRIPTION
        rule.status = True
        rule.type = "超限定用药"
        rule.save(update_fields=["drug_name", "description", "status", "type", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("rules", "0005_remove_rule_rule_name_rule_drug_name"),
    ]

    operations = [
        migrations.RunPython(
            add_entecavir_compile_example,
            migrations.RunPython.noop,
        ),
    ]
