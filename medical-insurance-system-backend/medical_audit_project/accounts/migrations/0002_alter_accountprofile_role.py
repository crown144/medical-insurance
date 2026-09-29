from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('accounts', '0001_initial')]

    operations = [
        migrations.AlterField(
            model_name='accountprofile',
            name='role',
            field=models.CharField(
                choices=[
                    ('normal', '普通用户'),
                    ('developer', '开发用户'),
                    ('admin', '应用管理员'),
                ],
                db_index=True,
                default='normal',
                max_length=20,
                verbose_name='系统角色',
            ),
        ),
    ]
