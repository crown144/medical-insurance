# rules/management/commands/import_rules.py

import json
from django.core.management.base import BaseCommand
from rules.models import Rule, MedicalCode
from django.db import transaction

class Command(BaseCommand):
    help = '从 JSON 文件导入药品代码和所有规则到数据库'

    def handle(self, *args, **options):
        
        # --- 第一部分：导入药品代码 (保持不变) ---
        self.stdout.write('开始导入药品代码...')
        try:
            with open('all_medical_data.json', 'r', encoding='utf-8') as f:
                medical_data = json.load(f)
            
            codes_to_create = [
                MedicalCode(code=item['code'], name=item['国家医保药品名称'])
                for item in medical_data if item.get('code') and item.get('国家医保药品名称')
            ]
            with transaction.atomic():
                MedicalCode.objects.bulk_create(codes_to_create, ignore_conflicts=True)
            self.stdout.write(self.style.SUCCESS(f'成功导入 {len(codes_to_create)} 条药品代码记录。'))
        except FileNotFoundError:
            self.stdout.write(self.style.WARNING('警告: all_medical_data.json 文件未找到，跳过药品代码导入。'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'导入药品代码时出错: {e}'))

        # --- 第二部分：从 result_limit_v2(1).json 导入规则 ---
        self.stdout.write('开始从 result_limit_v2(1).json 导入规则...')
        try:
            with open('result_limit_v2(1).json', 'r', encoding='utf-8') as f:
                rules_data = json.load(f)
            
            created_count = 0
            updated_count = 0
            
            with transaction.atomic():
                # rules_data 是一个字典，key 是药品名，value 是规则列表
                for drug_name, rule_list in rules_data.items():
                    if not isinstance(rule_list, list):
                        continue
                    
                    for rule_item in rule_list:
                        # 确保 rule_item 是一个字典
                        if not isinstance(rule_item, dict):
                            continue

                        rule_id = rule_item.get('ruleId')
                        if not rule_id:
                            continue

                        _, created = Rule.objects.update_or_create(
                            rule_id=rule_id,
                            defaults={
                                'drug_name': drug_name, # key 就是药品名称
                                'description': rule_item.get('ruleDescription', ''),
                                'logic_expression': rule_item.get('logicExpression', ''),
                                'status': True, # 默认为启用
                                'type': '超限定用药' # 默认为超限定用药
                            }
                        )
                        if created:
                            created_count += 1
                        else:
                            updated_count += 1
            
            self.stdout.write(self.style.SUCCESS(f'导入规则完成！新增 {created_count} 条，更新 {updated_count} 条。'))
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR('错误: result_limit_v2(1).json 文件未找到！请将其放在项目根目录。'))
        except json.JSONDecodeError:
            self.stdout.write(self.style.ERROR('错误: result_limit_v2(1).json 文件格式无效。'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'导入规则时出错: {e}'))