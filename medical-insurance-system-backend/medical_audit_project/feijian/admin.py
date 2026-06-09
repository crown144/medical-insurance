from django.contrib import admin

from .models import FeiJianImportBatch, FeiJianRawRecord


@admin.register(FeiJianImportBatch)
class FeiJianImportBatchAdmin(admin.ModelAdmin):
    list_display = ['id', 'file_name', 'status', 'record_count',
                    'success_count', 'error_count', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['file_name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(FeiJianRawRecord)
class FeiJianRawRecordAdmin(admin.ModelAdmin):
    list_display = ['id', 'import_batch', 'hospitalization_no', 'patient_name',
                    'hospital_name', 'issue_category', 'involved_amount',
                    'audit_task_id', 'created_at']
    list_filter = ['issue_category', 'import_batch']
    search_fields = ['hospitalization_no', 'patient_name', 'hospital_name']