from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='ParentChildRelation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('parent_insurance_code', models.CharField(blank=True, max_length=64, null=True, verbose_name='父项目医保统一编码')),
                ('parent_charge_code', models.CharField(db_index=True, max_length=64, verbose_name='父项目收费编码')),
                ('parent_name', models.CharField(max_length=255, verbose_name='父项目名称')),
                ('child_insurance_code', models.CharField(blank=True, max_length=64, null=True, verbose_name='子项目医保统一编码')),
                ('child_charge_code', models.CharField(db_index=True, max_length=64, verbose_name='子项目收费编码')),
                ('child_name', models.CharField(max_length=255, verbose_name='子项目名称')),
            ],
            options={
                'verbose_name': '父子项目映射',
                'verbose_name_plural': '父子项目映射',
            },
        ),
        migrations.AddIndex(
            model_name='parentchildrelation',
            index=models.Index(fields=['parent_charge_code', 'child_charge_code'], name='idx_parent_child_code'),
        ),
    ]