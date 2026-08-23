from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('performance', '0002_sync_evaluation_columns'),
    ]

    operations = [
        migrations.AddField(
            model_name='performanceevaluation',
            name='title',
            field=models.CharField(blank=True, default='', max_length=200, verbose_name='عنوان التقييم'),
        ),
        migrations.AddField(
            model_name='performanceevaluation',
            name='question_schema',
            field=models.JSONField(blank=True, default=list, verbose_name='أسئلة التقييم'),
        ),
        migrations.AlterField(
            model_name='performanceevaluation',
            name='feedback',
            field=models.TextField(blank=True, verbose_name='ملاحظات المدير'),
        ),
    ]
