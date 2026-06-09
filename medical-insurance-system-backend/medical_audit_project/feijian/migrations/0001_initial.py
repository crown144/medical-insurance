from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='FeiJianImportBatch',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID',
                )),
                ('file_name', models.CharField(
                    max_length=512, verbose_name='文件名',
                )),
                ('file_size', models.BigIntegerField(
                    default=0, verbose_name='文件大小(字节)',
                )),
                ('original_file', models.FileField(
                    blank=True, null=True,
                    upload_to='feijian_imports/%Y/%m/',
                    verbose_name='原始文件',
                )),
                ('status', models.CharField(
                    choices=[
                        ('uploading', '上传中'),
                        ('analyzing', '分析中'),
                        ('mapping', '待确认映射'),
                        ('importing', '导入中'),
                        ('success', '导入成功'),
                        ('failed', '导入失败'),
                    ],
                    db_index=True, default='uploading',
                    max_length=20, verbose_name='状态',
                )),
                ('record_count', models.IntegerField(
                    default=0, verbose_name='记录总数',
                )),
                ('success_count', models.IntegerField(
                    default=0, verbose_name='成功导入数',
                )),
                ('error_count', models.IntegerField(
                    default=0, verbose_name='失败数',
                )),
                ('error_detail', models.TextField(
                    blank=True, default='', verbose_name='错误详情',
                )),
                ('detected_columns', models.JSONField(
                    blank=True, default=list,
                    verbose_name='检测到的列名',
                )),
                ('column_mapping', models.JSONField(
                    blank=True, default=dict,
                    verbose_name='列映射关系',
                )),
                ('sample_rows', models.JSONField(
                    blank=True, default=list,
                    verbose_name='样本数据(前5行)',
                )),
                ('created_at', models.DateTimeField(
                    auto_now_add=True, verbose_name='创建时间',
                )),
                ('updated_at', models.DateTimeField(
                    auto_now=True, verbose_name='更新时间',
                )),
            ],
            options={
                'verbose_name': '飞检导入批次',
                'verbose_name_plural': '飞检导入批次',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='FeiJianRawRecord',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID',
                )),
                ('row_index', models.IntegerField(
                    default=0, verbose_name='行号',
                )),
                ('hospitalization_no', models.CharField(
                    db_index=True, max_length=64,
                    verbose_name='住院号',
                )),
                ('patient_name', models.CharField(
                    blank=True, default='', max_length=128,
                    verbose_name='患者姓名',
                )),
                ('hospital_name', models.CharField(
                    blank=True, default='', max_length=256,
                    verbose_name='医疗机构',
                )),
                ('admission_date', models.CharField(
                    blank=True, default='', max_length=32,
                    verbose_name='入院日期',
                )),
                ('discharge_date', models.CharField(
                    blank=True, default='', max_length=32,
                    verbose_name='出院日期',
                )),
                ('issue_category', models.CharField(
                    blank=True, default='', max_length=256,
                    verbose_name='问题类别',
                )),
                ('issue_description', models.TextField(
                    blank=True, default='', verbose_name='问题描述',
                )),
                ('involved_amount', models.DecimalField(
                    decimal_places=2, default=0, max_digits=14,
                    verbose_name='涉及金额',
                )),
                ('audit_org', models.CharField(
                    blank=True, default='', max_length=256,
                    verbose_name='飞检机构',
                )),
                ('audit_date', models.CharField(
                    blank=True, default='', max_length=32,
                    verbose_name='飞检日期',
                )),
                ('raw_data', models.JSONField(
                    blank=True, default=dict,
                    verbose_name='原始行数据',
                )),
                ('audit_task_id', models.CharField(
                    blank=True, default='', max_length=64,
                    verbose_name='关联审查任务ID',
                )),
                ('created_at', models.DateTimeField(
                    auto_now_add=True, verbose_name='创建时间',
                )),
                ('import_batch', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='records',
                    to='feijian.feijianimportbatch',
                    verbose_name='导入批次',
                )),
            ],
            options={
                'verbose_name': '飞检原始记录',
                'verbose_name_plural': '飞检原始记录',
                'ordering': ['import_batch', 'row_index'],
                'indexes': [
                    models.Index(
                        fields=['hospitalization_no'],
                        name='feijian_raw_hospita_idx',
                    ),
                    models.Index(
                        fields=['import_batch', 'row_index'],
                        name='feijian_raw_batch_row_idx',
                    ),
                ],
            },
        ),
    ]