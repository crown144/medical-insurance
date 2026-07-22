from rest_framework import serializers

from .models import SQLExecution, SQLRule


class SQLRuleSerializer(serializers.ModelSerializer):
    ruleName = serializers.CharField(source='rule_name')
    ruleType = serializers.CharField(source='rule_type')
    sqlContent = serializers.CharField(source='sql_content')
    sqlStatus = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = SQLRule
        fields = [
            'id',
            'ruleName',
            'ruleType',
            'description',
            'sqlContent',
            'remark',
            'sqlStatus',
            'createdAt',
            'updatedAt',
        ]

    def get_sqlStatus(self, obj):
        return '已配置' if str(obj.sql_content or '').strip() else '未配置'

    def to_internal_value(self, data):
        data = data.copy()
        aliases = {
            'rule_name': 'ruleName',
            'rule_type': 'ruleType',
            'sql_content': 'sqlContent',
            'created_at': 'createdAt',
            'updated_at': 'updatedAt',
        }
        for old_key, new_key in aliases.items():
            if old_key in data and new_key not in data:
                data[new_key] = data.pop(old_key)
        return super().to_internal_value(data)


class SQLExecutionSerializer(serializers.ModelSerializer):
    sqlRuleId = serializers.IntegerField(source='sql_rule_id', read_only=True)
    ruleName = serializers.CharField(source='sql_rule.rule_name', read_only=True)
    ruleType = serializers.CharField(source='sql_rule.rule_type', read_only=True)
    startDate = serializers.DateField(source='start_date', read_only=True)
    endDate = serializers.DateField(source='end_date', read_only=True)
    executeStatus = serializers.CharField(source='execute_status', read_only=True)
    executeTime = serializers.DateTimeField(source='execute_time', read_only=True)
    rowCount = serializers.IntegerField(source='row_count', read_only=True)
    resultJson = serializers.JSONField(source='result_json', read_only=True)
    errorMessage = serializers.CharField(source='error_message', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = SQLExecution
        fields = [
            'id',
            'sqlRuleId',
            'ruleName',
            'ruleType',
            'startDate',
            'endDate',
            'executeStatus',
            'executeTime',
            'duration',
            'rowCount',
            'resultJson',
            'errorMessage',
            'createdAt',
        ]


class SQLRuleExecutionSummarySerializer(serializers.ModelSerializer):
    ruleName = serializers.CharField(source='rule_name', read_only=True)
    ruleType = serializers.CharField(source='rule_type', read_only=True)
    recentExecuteTime = serializers.DateTimeField(source='recent_execute_time', read_only=True)
    executionCount = serializers.IntegerField(source='execution_count', read_only=True)
    totalViolationCount = serializers.IntegerField(source='total_violation_count', read_only=True)
    latestViolationCount = serializers.IntegerField(source='latest_violation_count', read_only=True)
    status = serializers.CharField(source='recent_execute_status', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = SQLRule
        fields = [
            'id',
            'ruleName',
            'ruleType',
            'recentExecuteTime',
            'executionCount',
            'totalViolationCount',
            'latestViolationCount',
            'status',
            'updatedAt',
        ]


class SQLRuleExecutionDetailSerializer(serializers.ModelSerializer):
    ruleName = serializers.CharField(source='rule_name', read_only=True)
    ruleType = serializers.CharField(source='rule_type', read_only=True)
    sqlContent = serializers.CharField(source='sql_content', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    recentExecuteTime = serializers.DateTimeField(source='recent_execute_time', read_only=True)
    executionCount = serializers.IntegerField(source='execution_count', read_only=True)
    totalViolationCount = serializers.IntegerField(source='total_violation_count', read_only=True)

    class Meta:
        model = SQLRule
        fields = [
            'id',
            'ruleName',
            'ruleType',
            'description',
            'sqlContent',
            'remark',
            'createdAt',
            'updatedAt',
            'recentExecuteTime',
            'executionCount',
            'totalViolationCount',
        ]
