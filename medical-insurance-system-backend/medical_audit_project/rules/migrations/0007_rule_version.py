from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('rules', '0006_rule_is_deleted')]
    operations = [migrations.AddField(model_name='rule', name='version', field=models.PositiveIntegerField(default=1, verbose_name='版本号'))]
