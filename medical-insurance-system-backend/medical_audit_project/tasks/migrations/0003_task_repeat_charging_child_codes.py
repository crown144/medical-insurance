from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0002_task_selected_schemas'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='repeat_charging_child_codes',
            field=models.JSONField(blank=True, default=list, verbose_name='重复收费选择的子规则医保编码'),
        ),
    ]