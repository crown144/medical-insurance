from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='SQLRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rule_name', models.CharField(db_index=True, max_length=255, unique=True, verbose_name='医保规则名称')),
                ('rule_type', models.CharField(db_index=True, max_length=100, verbose_name='规则类型')),
                ('description', models.TextField(blank=True, verbose_name='规则描述')),
                ('sql_content', models.TextField(verbose_name='SQL内容')),
                ('remark', models.TextField(blank=True, verbose_name='备注')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': 'SQL规则',
                'verbose_name_plural': 'SQL规则',
                'ordering': ['-updated_at', '-id'],
            },
        ),
        migrations.CreateModel(
            name='SQLExecution',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_date', models.DateField(verbose_name='开始日期')),
                ('end_date', models.DateField(verbose_name='结束日期')),
                ('execute_status', models.CharField(choices=[('success', '成功'), ('failed', '失败')], db_index=True, default='success', max_length=20, verbose_name='执行状态')),
                ('execute_time', models.DateTimeField(verbose_name='执行时间')),
                ('duration', models.PositiveIntegerField(default=0, verbose_name='执行耗时(毫秒)')),
                ('row_count', models.PositiveIntegerField(default=0, verbose_name='返回记录数')),
                ('result_json', models.JSONField(blank=True, default=dict, verbose_name='结果JSON')),
                ('error_message', models.TextField(blank=True, verbose_name='错误信息')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('sql_rule', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='executions', to='sql_analysis.sqlrule', verbose_name='SQL规则')),
            ],
            options={
                'verbose_name': 'SQL执行记录',
                'verbose_name_plural': 'SQL执行记录',
                'ordering': ['-execute_time', '-id'],
            },
        ),
    ]

