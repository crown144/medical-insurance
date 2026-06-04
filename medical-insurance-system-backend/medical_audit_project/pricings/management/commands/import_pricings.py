
import pandas as pd
from django.core.management.base import BaseCommand
from pricings.models import StandardChargeItem
from django.db import transaction
import numpy as np # 导入 numpy 来处理 NaN

class Command(BaseCommand):
    help = '从 Excel 文件导入标准收费项目价目表'

    def add_arguments(self, parser):
        parser.add_argument('excel_file', type=str, help='医保收费项目原始规则.xlsx 文件的路径')

    def handle(self, *args, **options):
        excel_file = options['excel_file']
        self.stdout.write(f'--- 正在从 Excel 文件读取数据: {excel_file} ---')
        
        try:
            # 读取 Excel，并将所有列都当作字符串读取，避免类型推断问题
            df = pd.read_excel(excel_file, dtype=str)
            
            # 将 pandas 识别的 <NA> 或 NaN 值替换为 None，以便存入数据库
            df = df.replace({np.nan: None})
            
            items_to_create = []
            
            # --- 核心改造点：使用你 Excel 中真实的列名 ---
            for index, row in df.iterrows():
                # 跳过没有收费编码的行
                if not row.get('收费编码'):
                    self.stdout.write(self.style.WARNING(f'警告: 第 {index+2} 行缺少“收费编码”，已跳过。'))
                    continue
                
                # 处理可能为空的数值字段
                try:
                    price_2021 = float(row.get('2021价格')) if row.get('2021价格') is not None else None
                except (ValueError, TypeError):
                    price_2021 = None

                try:
                    price_2024 = float(row.get('单价')) if row.get('单价') is not None else None
                except (ValueError, TypeError):
                    price_2024 = None
                
                items_to_create.append(
                    StandardChargeItem(
                        charge_code=row.get('收费编码'),
                        item_name=row.get('收费名称'), # 使用 '收费名称'
                        unit=row.get('单位'),
                        price_2021=price_2021,
                        price_2024=price_2024,
                        insurance_code=row.get('医保编码'),
                        description_2021=row.get('2021说明'),
                        description_2024=row.get('2024说明')
                    )
                )
            
            with transaction.atomic():
                self.stdout.write('--> 正在清空旧的价目表数据...')
                StandardChargeItem.objects.all().delete()
                self.stdout.write(f'--> 准备分批次导入 {len(items_to_create)} 条新记录...')
                StandardChargeItem.objects.bulk_create(items_to_create, batch_size=1000, ignore_conflicts=True)

            self.stdout.write(self.style.SUCCESS(f'--- 标准价目表导入成功！共处理 {len(items_to_create)} 条记录。 ---'))
            
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'错误: 文件 {excel_file} 未找到！'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'导入过程中发生严重错误: {e}'))