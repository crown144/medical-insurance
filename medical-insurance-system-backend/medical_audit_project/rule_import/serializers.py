from rest_framework import serializers

from .models import ExtractedRule, RuleImportTask


class RuleImportTaskSerializer(serializers.ModelSerializer):
    """任务序列化器（列表/详情/轮询）。"""
    status_label = serializers.CharField(
        source='get_status_display', read_only=True,
    )

    class Meta:
        model = RuleImportTask
        fields = [
            'id', 'task_name', 'status', 'status_label', 'stage', 'progress',
            'file_name', 'file_size', 'file_type', 'params',
            'table_count', 'rule_count', 'imported_count',
            'error_detail', 'celery_task_id',
            'created_at', 'updated_at', 'started_at', 'finished_at',
        ]
        read_only_fields = fields


class ExtractedRuleSerializer(serializers.ModelSerializer):
    """抽取规则序列化器。"""
    class Meta:
        model = ExtractedRule
        fields = [
            'id', 'import_task', 'seq', 'rule_type',
            'constrained_object', 'constraint_value', 'evidence', 'source',
            'is_selected', 'is_imported', 'imported_rule_id', 'created_at',
        ]


class UploadSerializer(serializers.Serializer):
    """上传并发起转换的请求参数校验。

    数量类参数（max_pdf_pages / max_rows_per_table / max_tables）均可不传，
    不传时表示“不限数量”（后端按 None 处理 = 全部）。
    LLM 分块行数(chunk_size)不在此暴露，仅由后端配置决定。
    """
    file = serializers.FileField()
    task_name = serializers.CharField(required=False, allow_blank=True,
                                      max_length=255)
    max_pdf_pages = serializers.IntegerField(required=False, allow_null=True,
                                             min_value=1)
    max_rows_per_table = serializers.IntegerField(required=False,
                                                  allow_null=True, min_value=1)
    max_tables = serializers.IntegerField(required=False, allow_null=True,
                                          min_value=1)


class ConfirmImportSerializer(serializers.Serializer):
    """确认入库请求参数校验。"""
    rule_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list,
    )
    select_all = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if not attrs.get('select_all') and not attrs.get('rule_ids'):
            raise serializers.ValidationError(
                "请提供 rule_ids 或将 select_all 设为 true"
            )
        return attrs
