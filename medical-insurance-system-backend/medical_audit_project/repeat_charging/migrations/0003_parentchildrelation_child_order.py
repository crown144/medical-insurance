from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('repeat_charging', '0002_alter_parentchildrelation_child_insurance_code_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='parentchildrelation',
            name='child_order',
            field=models.IntegerField(default=0, verbose_name='子项目顺序'),
        ),
        migrations.AddIndex(
            model_name='parentchildrelation',
            index=models.Index(fields=['parent_charge_code', 'child_order'], name='idx_parent_child_order'),
        ),
    ]