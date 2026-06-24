from django.contrib import admin

from .models import ExtractedRule, RuleImportTask


@admin.register(RuleImportTask)
class RuleImportTaskAdmin(admin.ModelAdmin):
    list_display = ['id', 'task_name', 'file_name', 'status', 'progress',
                    'table_count', 'rule_count', 'imported_count', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['task_name', 'file_name']
    readonly_fields = ['created_at', 'updated_at', 'started_at', 'finished_at']


@admin.register(ExtractedRule)
class ExtractedRuleAdmin(admin.ModelAdmin):
    list_display = ['id', 'import_task', 'seq', 'rule_type',
                    'constrained_object', 'is_selected', 'is_imported',
                    'imported_rule_id', 'created_at']
    list_filter = ['rule_type', 'is_imported', 'is_selected']
    search_fields = ['constrained_object', 'constraint_value']
