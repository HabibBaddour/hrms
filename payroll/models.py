from decimal import Decimal

from django.db import models

class Payroll(models.Model):
    # تم استبدال الاستيراد المباشر بـ 'employees.Employee' كنص لمنع خطأ Import عند الإقلاع
    employee = models.ForeignKey('employees.Employee', on_delete=models.CASCADE, related_name='payrolls', verbose_name="الموظف")
    month = models.PositiveIntegerField(verbose_name="الشهر")
    year = models.PositiveIntegerField(verbose_name="السنة")
    
    basic_salary = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="الراتب الأساسي")
    allowances = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="البدلات")
    bonuses = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="المكافآت")
    overtime_pay = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="أجر العمل الإضافي")

    # الخصومات
    deductions_absence = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="خصم الغياب")
    deductions_delay = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="خصم التأخير")
    insurance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="التأمينات")
    other_deductions = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="خصومات أخرى")

    # بيانات الصرف / الحوالة
    PAYMENT_CHOICES = (
        ('BANK', 'تحويل بنكي'),
        ('CASH', 'صرف نقدي'),
    )
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default='BANK', verbose_name="طريقة الصرف")
    bank_name = models.CharField(max_length=100, blank=True, verbose_name="اسم البنك")
    account_number = models.CharField(max_length=40, blank=True, verbose_name="رقم الحساب / الآيبان")

    net_salary = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="صافي الراتب")
    STATUS_CHOICES = (
        ('PAID', 'مدفوع'),
        ('PENDING', 'معلق'),
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING', verbose_name="حالة الصرف")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('employee', 'month', 'year')
        verbose_name = "مسرد راتب"
        verbose_name_plural = "كشوف الرواتب"

    def save(self, *args, **kwargs):
        # حساب صافي الراتب تلقائياً عند الحفظ
        self.net_salary = self.total_earnings - self.total_deductions
        super().save(*args, **kwargs)

    @property
    def total_deductions(self):
        return self.deductions_absence + self.deductions_delay + self.insurance + self.other_deductions

    @property
    def total_earnings(self):
        return self.basic_salary + self.allowances + self.bonuses + self.overtime_pay

    @property
    def gross_salary(self):
        return self.total_earnings

    @property
    def month_display(self):
        names = {1: 'يناير', 2: 'فبراير', 3: 'مارس', 4: 'أبريل', 5: 'مايو', 6: 'يونيو',
                 7: 'يوليو', 8: 'أغسطس', 9: 'سبتمبر', 10: 'أكتوبر', 11: 'نوفمبر', 12: 'ديسمبر'}
        return names.get(self.month, self.month)

    def sync_payslip(self):
        # نسخ بيانات المسير إلى قسيمة العرض الديناميكية (نموذج Payslip بنظام المستحقات والاستقطاعات)
        from employees.models import Payslip, PayslipEarning, PayslipDeduction
        payslip, _ = Payslip.objects.get_or_create(
            employee=self.employee, month=self.month, year=self.year,
            defaults={'basic_salary': self.basic_salary},
        )
        payslip.basic_salary = self.basic_salary
        payslip.payment_method = self.payment_method
        payslip.bank_name = self.bank_name or ''
        payslip.account_number = self.account_number or ''
        payslip.save()

        payslip.earnings.all().delete()
        payslip.deductions.all().delete()

        earnings_specs = (
            ('allowances', 'بدلات'),
            ('bonuses', 'مكافآت وحوافز'),
            ('overtime_pay', 'أجر العمل الإضافي'),
        )
        for field, title in earnings_specs:
            amount = getattr(self, field)
            if amount:
                PayslipEarning.objects.create(payslip=payslip, title=title, amount=amount)

        deductions_specs = (
            ('deductions_absence', 'خصم الغياب'),
            ('deductions_delay', 'خصم التأخير'),
            ('insurance', 'التأمينات الاجتماعية'),
            ('other_deductions', 'خصومات أخرى / سلف'),
        )
        for field, title in deductions_specs:
            amount = getattr(self, field)
            if amount:
                PayslipDeduction.objects.create(payslip=payslip, title=title, amount=amount)
        return payslip

    def __str__(self):
        return f"قسيمة راتب {self.employee} - {self.month}/{self.year}"