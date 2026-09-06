# Manually written: Payslip payment info fields (display side of payroll sync)
# Generated for Django 6.0.7

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0012_payslip_payslipdeduction_payslipearning'),
    ]

    operations = [
        migrations.AddField(
            model_name='payslip',
            name='payment_method',
            field=models.CharField(choices=[('BANK', 'تحويل بنكي'), ('CASH', 'صرف نقدي')], default='BANK', max_length=10, verbose_name='طريقة الصرف'),
        ),
        migrations.AddField(
            model_name='payslip',
            name='bank_name',
            field=models.CharField(blank=True, max_length=100, verbose_name='اسم البنك'),
        ),
        migrations.AddField(
            model_name='payslip',
            name='account_number',
            field=models.CharField(blank=True, max_length=40, verbose_name='رقم الحساب / الآيبان'),
        ),
    ]