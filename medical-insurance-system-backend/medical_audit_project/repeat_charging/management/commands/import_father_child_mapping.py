"""
从CSV导入父子项目编码映射到数据库

用法：
python manage.py import_father_child_mapping --csv "d:\\medical 3\\1016_type1\\father-child.csv"
"""

import csv
from django.core.management.base import BaseCommand, CommandError

from repeat_charging.models import ParentChildRelation


class Command(BaseCommand):
    help = '导入父子项目映射(CSV)到数据库'

    def add_arguments(self, parser):
        parser.add_argument('--csv', type=str, required=True, help='CSV文件路径')
        parser.add_argument('--truncate', action='store_true', help='导入前清空现有映射')

    def handle(self, *args, **options):
        csv_path = options['csv']
        truncate = options['truncate']

        try:
            if truncate:
                ParentChildRelation.objects.all().delete()
                self.stdout.write(self.style.WARNING('已清空现有父子映射'))

            count = 0
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    parent_charge_code = (row.get('收费编码') or row.get('父项目收费编码') or '').strip()
                    child_charge_code = (row.get('子项目收费编码') or '').strip()
                    parent_name = (row.get('父项目名称') or '').strip()
                    child_name = (row.get('子项目名称') or '').strip()
                    parent_ins_code = (row.get('医保统一编码') or row.get('父项目医保编码') or '').strip()
                    child_ins_code = (row.get('子项目医保编码') or '').strip()

                    if not parent_charge_code or not child_charge_code:
                        continue

                    ParentChildRelation.objects.update_or_create(
                        parent_charge_code=parent_charge_code,
                        child_charge_code=child_charge_code,
                        defaults={
                            'parent_name': parent_name or parent_charge_code,
                            'child_name': child_name or child_charge_code,
                            'parent_insurance_code': parent_ins_code or None,
                            'child_insurance_code': child_ins_code or None,
                        }
                    )
                    count += 1

            self.stdout.write(self.style.SUCCESS(f'导入完成，共 {count} 条映射'))
        except FileNotFoundError:
            raise CommandError(f'CSV文件未找到: {csv_path}')
        except Exception as e:
            raise CommandError(f'导入失败: {e}')