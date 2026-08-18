from django.db import models

class Payroll(models.Model):
    # تم استبدال الاستيراد المباشر بـ 'employees.Employee' كنص لمنع خطأ Import عند الإقلاع
    employee = models.ForeignKey('employees.Employee', on_delete=models.CASCADE, related_name='payrolls', verbose_name="الموظف")
    month = models.PositiveIntegerField(verbose_name="الشهر")
    year = models.PositiveIntegerField(verbose_name="السنة")
    
    basic_salary = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="الراتب الأساسي")
    allowances = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="البدلات")
    
    # الخصومات
    deductions_absence = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="خصم الغياب")
    deductions_delay = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="خصم التأخير")
    insurance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="التأمينات")
    other_deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="خصومات أخرى")
    
    net_salary = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="صافي الراتب")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('employee', 'month', 'year')
        verbose_name = "مسرد راتب"
        verbose_name_plural = "كشوف الرواتب"

    def save(self, *args, **kwargs):
        # حساب صافي الراتب تلقائياً عند الحفظ
        total_deductions = (self.deductions_absence + self.deductions_delay + 
                            self.insurance + self.other_deductions)
        self.net_salary = (self.basic_salary + self.allowances) - total_deductions
        super().save(*args, **kwargs)

    def __str__(self):
        return f"قسيمة راتب {self.employee} - {self.month}/{self.year}"