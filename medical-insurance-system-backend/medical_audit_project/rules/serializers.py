from rest_framework import serializers

from .models import Rule


class RuleSerializer(serializers.ModelSerializer):
    enabled = serializers.BooleanField(source='status')
    logicExpression = serializers.CharField(source='logic_expression')
    drugName = serializers.CharField(source='drug_name')
    ruleId = serializers.CharField(source='rule_id')

    class Meta:
        model = Rule
        fields = ['id', 'drugName', 'ruleId', 'description', 'logicExpression', 'enabled', 'type', 'rule_code']
