from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('payroll', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.AddField(
                    model_name='payroll',
                    name='bonuses',
                    field=models.DecimalField(
                        decimal_places=2,
                        default=0.0,
                        max_digits=10,
                        verbose_name='المكافآت',
                    ),
                ),
            ],
            state_operations=[],
        ),
    ]
