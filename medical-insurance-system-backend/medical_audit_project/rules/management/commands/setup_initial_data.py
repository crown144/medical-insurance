# rules/management/commands/setup_initial_data.py

from django.core.management.base import BaseCommand
from rules.models import AuditTemplate
import json

class Command(BaseCommand):
    help = '设置项目的初始数据，例如审核模板'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('--> 开始设置初始数据...'))
        
        self.setup_audit_templates()
        
        # 未来你还可以增加其他初始化函数，比如 setup_default_users()
        
        self.stdout.write(self.style.SUCCESS('--> 初始数据设置完成！'))

    def setup_audit_templates(self):
        """创建或更新审核模板"""
        self.stdout.write('  -> 正在创建或更新审核模板...')
        
        template_content = {
            "templateId": "medication_template",
            "description": "用药审查模板",
            "steps": [
                {
                    "stepId": "extract_medication",
                    "type": "field_extraction",
                    "path": "用药信息.治疗用药",
                    "outputVariable": "medications"
                },
                {
                    "stepId": "loop_medication",
                    "type": "loop",
                    "collection": "medications",
                    "itemVariable": "current_med",
                    "steps": [
                        {
                            "stepId": "find_rule",
                            "type": "rule_lookup",
                            "ruleLookup": {
                                "key": "current_med.医保药品代码-国家"
                            }
                        }
                    ]
                }
            ]
        }

        template_obj, created = AuditTemplate.objects.update_or_create(
            template_id='medication_template',
            defaults={
                'description': '用药审查模板',
                'template_json': template_content
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS("    - 模板 'medication_template' 已成功创建！"))
        else:
            self.stdout.write(self.style.WARNING("    - 模板 'medication_template' 已存在，已更新。"))