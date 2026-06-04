# Generated migration for adding rule_code fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rules', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='rule',
            name='rule_code',
            field=models.TextField(blank=True, help_text='Python函数代码字符串，定义 execute_rule(medical_record, current_item) 函数', verbose_name='规则代码'),
        ),
        migrations.AddField(
            model_name='rule',
            name='match_field',
            field=models.CharField(blank=True, help_text='用于匹配的字段名，如 \'收费项目名称\' 或 \'收费项目代码\'', max_length=50, verbose_name='匹配字段'),
        ),
        migrations.AddField(
            model_name='rule',
            name='match_value',
            field=models.CharField(blank=True, db_index=True, help_text='匹配字段的值，如药品名称或代码', max_length=255, verbose_name='匹配值'),
        ),
        migrations.AlterField(
            model_name='rule',
            name='drug_name',
            field=models.CharField(blank=True, db_index=True, help_text='药品名称或收费项目名称，用于匹配', max_length=255, verbose_name='药品名称'),
        ),
        migrations.AlterField(
            model_name='rule',
            name='logic_expression',
            field=models.TextField(blank=True, help_text='旧版逻辑表达式（已弃用，保留用于兼容）', verbose_name='逻辑表达式'),
        ),
    ]

