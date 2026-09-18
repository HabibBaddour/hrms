# Manually written: Employee personal email + single secondary/emergency phone
# Generated for Django 6.0.7

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0013_payslip_payment_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='personal_email',
            field=models.EmailField(blank=True, max_length=254, null=True, verbose_name='البريد الإلكتروني الشخصي'),
        ),
        migrations.AddField(
            model_name='employee',
            name='phone_secondary',
            field=models.CharField(blank=True, max_length=20, null=True, verbose_name='رقم الهاتف الإضافي / الطوارئ'),
        ),
    ]