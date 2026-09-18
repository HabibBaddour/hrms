from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('performance', '0009_evaluationdraft'),
    ]

    operations = [
        migrations.AddField(
            model_name='performancequestion',
            name='is_na',
            field=models.BooleanField(default=False, help_text='سؤال إعلامي لا يُحتسب ضمن درجات التقييم.', verbose_name='غير قابل للتقييم'),
        ),
        migrations.AddField(
            model_name='performancequestion',
            name='tag',
            field=models.CharField(blank=True, choices=[('essential', 'أساسي'), ('target', 'مستهدف')], default='', max_length=10, verbose_name='وسم المهارة'),
        ),
    ]