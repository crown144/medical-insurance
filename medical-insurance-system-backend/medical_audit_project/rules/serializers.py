from rest_framework import serializers

from .models import Rule


class RuleSerializer(serializers.ModelSerializer):
    enabled = serializers.BooleanField(source='status', required=False)
    logicExpression = serializers.CharField(
        source='logic_expression',
        required=False,
        allow_blank=True,
    )
    drugName = serializers.CharField(source='drug_name', allow_blank=True)
    ruleId = serializers.CharField(source='rule_id', required=False)

    class Meta:
        model = Rule
        fields = [
            'id',
            'drugName',
            'ruleId',
            'description',
            'logicExpression',
            'enabled',
            'type',
            'rule_code',
            'created_at',
            'updated_at',
        ]

    @staticmethod
    def _has_rule_code(value):
        if value is None:
            return False
        return bool(str(value).strip())

    def to_internal_value(self, data):
        data = data.copy()
        if 'drug_name' in data and 'drugName' not in data:
            data['drugName'] = data.pop('drug_name')
        if 'rule_id' in data and 'ruleId' not in data:
            data['ruleId'] = data.pop('rule_id')
        if 'logic_expression' in data and 'logicExpression' not in data:
            data['logicExpression'] = data.pop('logic_expression')
        if 'status' in data and 'enabled' not in data:
            data['enabled'] = data.pop('status')
        if 'ruleCode' in data and 'rule_code' not in data:
            data['rule_code'] = data.pop('ruleCode')
        if not data.get('ruleId'):
            from django.utils import timezone

            data['ruleId'] = f"R-{timezone.now().strftime('%Y%m%d%H%M%S%f')}"
        data.setdefault('logicExpression', '')
        data.setdefault('enabled', True)
        return super().to_internal_value(data)

    def validate(self, attrs):
        attrs = super().validate(attrs)

        next_status = attrs.get('status')
        if next_status is None and self.instance is not None:
            next_status = self.instance.status

        next_rule_code = attrs.get('rule_code')
        if next_rule_code is None and self.instance is not None:
            next_rule_code = self.instance.rule_code

        if next_status and not self._has_rule_code(next_rule_code):
            raise serializers.ValidationError({
                'enabled': '规则未生成执行代码，无法启用',
            })

        return attrs
