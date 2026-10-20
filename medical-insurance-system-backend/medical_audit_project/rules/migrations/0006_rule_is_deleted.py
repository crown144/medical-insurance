from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rules', '0005_remove_rule_rule_name_rule_drug_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='rule',
            name='is_deleted',
            field=models.BooleanField(db_index=True, default=False, verbose_name='是否已删除'),
        ),
    ]
