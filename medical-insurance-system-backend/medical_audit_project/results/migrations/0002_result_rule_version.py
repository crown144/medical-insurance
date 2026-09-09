from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('results', '0001_initial'), ('rules', '0007_rule_version')]
    operations = [migrations.AddField(model_name='result', name='rule_version', field=models.PositiveIntegerField(db_index=True, default=1, verbose_name='命中规则版本'))]
