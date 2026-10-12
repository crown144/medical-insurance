from rest_framework import serializers
from django.conf import settings
from .models import Task
from rules.models import Rule
from rules.serializers import RuleSerializer

DEMO_RULE_IDS = [
    'R-0001',
    'R-0002',
    'R-20260704151155530323',
    'R-20260704151155864177',
    'R-20260704151200686615',
    'R-20260704151201033234',
    'R-20260704151207016105',
    'R-20260704151207710658',
    'R-20260709123055310514',
    'R-20260709124003677192',
]


def get_demo_rule_ids(selected_schemas):
    qs = Rule.objects.filter(rule_id__in=DEMO_RULE_IDS)
    if selected_schemas:
        qs = qs.filter(type__in=selected_schemas)
    return list(qs.values_list('id', flat=True))


def infer_schemas_from_rule_ids(rule_ids):
    schemas = []
    for rule_type in Rule.objects.filter(id__in=rule_ids).values_list('type', flat=True):
        if rule_type and rule_type not in schemas:
            schemas.append(rule_type)
    return schemas


class TaskSerializer(serializers.ModelSerializer):
    rules = RuleSerializer(many=True, read_only=True)

    rule_ids = serializers.ListField(
        # 【修改1】改为非必须，以支持只选“超标准收费”等方案
        child=serializers.IntegerField(), write_only=True, required=False
    )

    # 这里的 source='selected_schemas' 非常关键
    # 它告诉 DRF：前端会传来一个叫 'selectedSchemas' 的字段，
    # 但在 validated_data 里，请把它变成 'selected_schemas' (小写)
    selectedSchemas = serializers.ListField(
        child=serializers.CharField(), source='selected_schemas', required=False
    )

    # 新增：重复收费子规则医保编码列表
    repeatChargingChildCodes = serializers.ListField(
        child=serializers.CharField(), source='repeat_charging_child_codes', write_only=True, required=False
    )

    # 新增：重复收费父-子医保编码对列表（格式："父/子"）
    repeatChargingPairs = serializers.ListField(
        child=serializers.CharField(), source='repeat_charging_pairs', write_only=True, required=False
    )

    class Meta:
        model = Task
        fields = ['id', 'name', 'status', 'hospitalization_ids', 'mdc_org_cd', 'summary', 'self_reflection',
                  'created_at', 'started_at', 'completed_at', 'rules',
                  'rule_ids', 'selectedSchemas', 'repeatChargingChildCodes', 'repeatChargingPairs']
        read_only_fields = ['status', 'summary', 'self_reflection', 'created_at', 'started_at', 'completed_at', 'rules']

    def to_internal_value(self, data):
        data = data.copy()
        if 'selected_schemas' in data and 'selectedSchemas' not in data:
            data['selectedSchemas'] = data.pop('selected_schemas')
        return super().to_internal_value(data)

    def create(self, validated_data):
        # 1. 从验证数据中安全地 pop 出 'rule_ids'
        #    如果前端没传，默认为空列表
        rule_ids = validated_data.pop('rule_ids', [])

        # 2. 【核心修正】同样，从验证数据中 pop 出 'selected_schemas'
        #    因为有 source 映射，它在 validated_data 里的 key 是小写的 'selected_schemas'
        selected_schemas_data = validated_data.pop('selected_schemas', [])
        if not rule_ids:
            rule_ids = get_demo_rule_ids(selected_schemas_data)
        if not selected_schemas_data:
            selected_schemas_data = infer_schemas_from_rule_ids(rule_ids)
        repeat_child_codes = validated_data.pop('repeat_charging_child_codes', [])
        repeat_pairs = validated_data.pop('repeat_charging_pairs', [])
        validated_data['mdc_org_cd'] = (
            str(validated_data.get('mdc_org_cd') or getattr(settings, 'SOURCE_MDC_ORG_CD', '')).strip()
        )

        # 3. 现在 validated_data 里只剩下 Task 模型可以直接接受的字段
        task = Task.objects.create(**validated_data)

        # 4. 【核心修正】手动为新创建的 task 对象的 selected_schemas 字段赋值
        task.selected_schemas = selected_schemas_data
        task.repeat_charging_child_codes = repeat_child_codes
        task.repeat_charging_pairs = repeat_pairs

        # 5. 如果有 rule_ids，就设置多对多关系
        if rule_ids:
            task.rules.set(rule_ids)

        inferred_schemas = infer_schemas_from_rule_ids(
            list(task.rules.values_list('id', flat=True)),
        )
        if inferred_schemas:
            task.selected_schemas = inferred_schemas

        # 6. 【核心修正】显式地调用 save() 来确保所有字段都被写入数据库
        #    这会同时保存 selected_schemas 和多对多关系
        task.save()

        return task

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not data.get('selectedSchemas'):
            schemas = []
            rules = data.get('rules') or []
            for rule in rules:
                rule_type = rule.get('type')
                if rule_type and rule_type not in schemas:
                    schemas.append(rule_type)
            if not schemas:
                schemas = infer_schemas_from_rule_ids(get_demo_rule_ids([]))
            data['selectedSchemas'] = schemas
        return data
