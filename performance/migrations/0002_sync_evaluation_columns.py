from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('performance', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.AddField(
                    model_name='performanceevaluation',
                    name='period_type',
                    field=models.CharField(
                        choices=[('ANNUAL', 'سنوي'), ('SEMI_ANNUAL', 'نصف سنوي')],
                        default='ANNUAL',
                        max_length=20,
                        verbose_name='نوع الفترة',
                    ),
                ),
                migrations.AddField(
                    model_name='performanceevaluation',
                    name='status',
                    field=models.CharField(
                        choices=[('DRAFT', 'مسودة'), ('COMPLETED', 'مكتمل')],
                        default='COMPLETED',
                        max_length=20,
                        verbose_name='الحالة',
                    ),
                ),
                migrations.AddField(
                    model_name='performanceevaluation',
                    name='employee_feedback',
                    field=models.TextField(blank=True, verbose_name='رد الموظف'),
                ),
                migrations.AddField(
                    model_name='performanceevaluation',
                    name='updated_at',
                    field=models.DateTimeField(auto_now=True),
                ),
            ],
            state_operations=[],
        ),
    ]
