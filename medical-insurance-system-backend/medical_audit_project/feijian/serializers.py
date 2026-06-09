from rest_framework import serializers

from .models import FeiJianImportBatch, FeiJianRawRecord


class FeiJianImportBatchSerializer(serializers.ModelSerializer):
    """导入批次序列化器"""
    status_label = serializers.CharField(
        source='get_status_display', read_only=True,
    )

    class Meta:
        model = FeiJianImportBatch
        fields = [
            'id', 'file_name', 'file_size', 'status', 'status_label',
            'record_count', 'success_count', 'error_count', 'error_detail',
            'detected_columns', 'column_mapping', 'sample_rows',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'file_size', 'status', 'status_label',
            'record_count', 'success_count', 'error_count', 'error_detail',
            'detected_columns', 'column_mapping', 'sample_rows',
            'created_at', 'updated_at',
        ]


class FeiJianRawRecordSerializer(serializers.ModelSerializer):
    """原始记录序列化器"""
    import_file_name = serializers.CharField(
        source='import_batch.file_name', read_only=True,
    )

    class Meta:
        model = FeiJianRawRecord
        fields = [
            'id', 'import_batch', 'import_file_name', 'row_index',
            'hospitalization_no', 'patient_name', 'hospital_name',
            'admission_date', 'discharge_date',
            'issue_category', 'issue_description',
            'involved_amount', 'audit_org', 'audit_date',
            'audit_task_id', 'raw_data', 'created_at',
        ]


class FileUploadSerializer(serializers.Serializer):
    """文件上传序列化器"""
    file = serializers.FileField()


class ColumnMappingSerializer(serializers.Serializer):
    """列映射确认序列化器"""
    batch_id = serializers.IntegerField()
    column_mapping = serializers.DictField(
        child=serializers.CharField(),
        help_text='字段映射，如 {"hospitalization_no": "住院号", ...}'
    )


class PreviewRequestSerializer(serializers.Serializer):
    """预览请求序列化器"""
    batch_id = serializers.IntegerField()
    column_mapping = serializers.DictField(
        child=serializers.CharField(),
    )
    limit = serializers.IntegerField(default=10, max_value=50)


class BuildAuditTaskSerializer(serializers.Serializer):
    """从飞检导入批次构建自动审查任务的请求参数。"""
    name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    selectedSchemas = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=False,
    )
    rule_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
    )
    execute = serializers.BooleanField(required=False, default=True)
