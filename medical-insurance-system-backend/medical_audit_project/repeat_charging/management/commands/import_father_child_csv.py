import csv
from django.core.management.base import BaseCommand, CommandError
from repeat_charging.models import ParentChildRelation
from django.db.models import Q
import re
from pathlib import Path


class Command(BaseCommand):
    help = "Import father-child rules from a CSV file into ParentChildRelation"

    def add_arguments(self, parser):
        parser.add_argument('--path', type=str, default=str(Path.cwd().parent / '1016_type1' / 'father-child.csv'),
                            help='Path to father-child.csv')
        parser.add_argument('--encoding', type=str, default='utf-8', help='CSV file encoding')
        parser.add_argument('--overwrite', action='store_true', help='Overwrite existing rows for same parent/child codes')

    def handle(self, *args, **options):
        csv_path = Path(options['path'])
        encoding = options['encoding']
        overwrite = options['overwrite']

        if not csv_path.exists():
            raise CommandError(f"CSV not found: {csv_path}")

        self.stdout.write(self.style.NOTICE(f"Importing CSV: {csv_path}"))

        count = 0
        with csv_path.open('r', encoding=encoding, newline='') as f:
            reader = csv.DictReader(f)
            # 处理可能存在的 BOM
            if reader.fieldnames:
                reader.fieldnames = [h.lstrip('\ufeff').strip() for h in reader.fieldnames]
            required_headers = [
                '医保统一编码', '收费编码', '父项目名称',
                '子项目医保编码', '子项目收费编码', '子项目名称'
            ]
            for h in required_headers:
                if h not in reader.fieldnames:
                    raise CommandError(f"Missing header '{h}' in CSV. Headers: {reader.fieldnames}")

            for row in reader:
                parent_ins = (row.get('医保统一编码') or '').strip()
                parent_charge = (row.get('收费编码') or '').strip()
                parent_name = (row.get('父项目名称') or '').strip()
                child_ins_raw = (row.get('子项目医保编码') or '').strip()
                child_charge_raw = (row.get('子项目收费编码') or '').strip()
                child_name_raw = (row.get('子项目名称') or '').strip()

                # 拆分子项目为多条，分隔符支持英文分号/中文分号
                splitter = r'[;；]'
                child_ins_list = [s.strip() for s in re.split(splitter, child_ins_raw) if s.strip()]
                child_charge_list = [s.strip() for s in re.split(splitter, child_charge_raw) if s.strip()]
                child_name_list = [s.strip() for s in re.split(splitter, child_name_raw) if s.strip()]

                # 基础校验
                if not parent_charge:
                    # 缺少父收费编码，跳过
                    continue
                if not child_ins_list and not child_charge_list and not child_name_list:
                    # 没有任何子项信息，跳过
                    continue
                # 长度必须一致（保持原始数据的顺序对应关系）
                max_len = max(len(child_ins_list), len(child_charge_list), len(child_name_list))
                if not (len(child_ins_list) == len(child_charge_list) == len(child_name_list) == max_len):
                    raise CommandError(
                        f"子项列长度不一致: 医保={len(child_ins_list)}, 收费={len(child_charge_list)}, 名称={len(child_name_list)}; 父编码={parent_charge}"
                    )

                for i in range(max_len):
                    c_ins = child_ins_list[i] if i < len(child_ins_list) else ''
                    c_charge = child_charge_list[i] if i < len(child_charge_list) else ''
                    c_name = child_name_list[i] if i < len(child_name_list) else ''
                    if not c_charge:
                        # 子收费编码缺失，不落库
                        continue
                    if overwrite:
                        ParentChildRelation.objects.update_or_create(
                            parent_charge_code=parent_charge,
                            child_charge_code=c_charge,
                            defaults={
                                'parent_insurance_code': parent_ins,
                                'parent_name': parent_name,
                                'child_insurance_code': c_ins,
                                'child_name': c_name,
                                'child_order': i,
                            }
                        )
                    else:
                        ParentChildRelation.objects.get_or_create(
                            parent_charge_code=parent_charge,
                            child_charge_code=c_charge,
                            defaults={
                                'parent_insurance_code': parent_ins,
                                'parent_name': parent_name,
                                'child_insurance_code': c_ins,
                                'child_name': c_name,
                                'child_order': i,
                            }
                        )
                    count += 1

        # 清理可能遗留的“聚合”记录（含分号的编码），仅在覆盖模式下执行
        if overwrite:
            deleted = ParentChildRelation.objects.filter(
                Q(child_charge_code__contains=';') | Q(child_insurance_code__contains=';')
            ).delete()
            self.stdout.write(self.style.NOTICE(f"Cleanup aggregated rows: deleted {deleted[0]} rows"))

        self.stdout.write(self.style.SUCCESS(f"Imported {count} rows into ParentChildRelation"))