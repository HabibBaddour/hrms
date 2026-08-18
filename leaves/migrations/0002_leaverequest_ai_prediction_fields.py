from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leaves', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='leaverequest',
            name='ai_prediction',
            field=models.CharField(
                choices=[('APPROVED', 'مقبول'), ('REJECTED', 'مرفوض'), ('PENDING', 'قيد التحليل')],
                default='PENDING',
                max_length=20,
                verbose_name='توصية الذكاء الاصطناعي',
            ),
        ),
        migrations.AddField(
            model_name='leaverequest',
            name='ai_confidence',
            field=models.FloatField(default=0.0, verbose_name='نسبة الثقة'),
        ),
    ]
