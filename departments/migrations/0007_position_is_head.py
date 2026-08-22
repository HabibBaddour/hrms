from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('departments', '0006_position_salary_max_position_salary_min'),
    ]

    operations = [
        migrations.AddField(
            model_name='position',
            name='is_head',
            field=models.BooleanField(default=False, verbose_name='رئيس القسم'),
        ),
    ]