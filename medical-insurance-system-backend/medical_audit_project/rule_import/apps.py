from django.apps import AppConfig


class RuleImportConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'rule_import'
    verbose_name = '规则批量导入转换'
