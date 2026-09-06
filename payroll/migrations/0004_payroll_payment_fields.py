# Manually written: payroll payment + overtime fields (Payroll architecture sync)
# Generated for Django 6.0.7

from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0003_payroll_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='payroll',
            name='overtime_pay',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='أجر العمل الإضافي'),
        ),
        migrations.AddField(
            model_name='payroll',
            name='payment_method',
            field=models.CharField(choices=[('BANK', 'تحويل بنكي'), ('CASH', 'صرف نقدي')], default='BANK', max_length=10, verbose_name='طريقة الصرف'),
        ),
        migrations.AddField(
            model_name='payroll',
            name='bank_name',
            field=models.CharField(blank=True, max_length=100, verbose_name='اسم البنك'),
        ),
        migrations.AddField(
            model_name='payroll',
            name='account_number',
            field=models.CharField(blank=True, max_length=40, verbose_name='رقم الحساب / الآيبان'),
        ),
    ]