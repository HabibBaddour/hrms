from django.db import models
from django.urls import reverse
from datetime import date, datetime

class LeaveRequest(models.Model):
    class LeaveType(models.TextChoices):
        ANNUAL = 'ANNUAL', 'سنوية'
        SICK = 'SICK', 'مرضية'
        UNPAID = 'UNPAID', 'بدون راتب'
        EMERGENCY = 'EMERGENCY', 'طارئة'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'قيد الانتظار'
        APPROVED = 'APPROVED', 'مقبولة'
        REJECTED = 'REJECTED', 'مرفوضة'

    # تم استبدال الاستيراد المباشر بـ 'employees.Employee' كنص لمنع خطأ Import عند الإقلاع
    employee = models.ForeignKey('employees.Employee', on_delete=models.CASCADE, related_name='leave_requests', verbose_name="الموظف")
    leave_type = models.CharField(max_length=15, choices=LeaveType.choices, verbose_name="نوع الإجازة")
    start_date = models.DateField(verbose_name="تاريخ البداية")
    end_date = models.DateField(verbose_name="تاريخ النهاية")
    reason = models.TextField(verbose_name="سبب الإجازة")
    attachment = models.FileField(upload_to='leave_attachments/', null=True, blank=True, verbose_name="المرفق")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, verbose_name="حالة الطلب")
    ai_prediction = models.CharField(max_length=20, choices=[('APPROVED', 'مقبول'), ('REJECTED', 'مرفوض'), ('PENDING', 'قيد التحليل')], default='PENDING', verbose_name="توصية الذكاء الاصطناعي")
    ai_confidence = models.FloatField(default=0.0, verbose_name="نسبة الثقة")
    
    approved_by = models.ForeignKey('employees.Employee', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_leaves', verbose_name="الموافق عليهم")
    manager_notes = models.TextField(blank=True, null=True, verbose_name="ملاحظات المدير")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "طلب إجازة"
        verbose_name_plural = "طلبات الإجازات"

    @property
    def total_days(self):
        if not self.end_date or not self.start_date:
            return 0
        start_date = self.start_date
        end_date = self.end_date
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        if isinstance(start_date, datetime):
            start_date = start_date.date()
        if isinstance(end_date, datetime):
            end_date = end_date.date()
        if isinstance(start_date, date) and isinstance(end_date, date):
            return (end_date - start_date).days + 1
        return 0

    def __str__(self):
        return f"{self.employee} - {self.get_leave_type_display()} ({self.get_status_display()})"

    def get_absolute_url(self):
        return reverse('leaves:approve_leave', kwargs={'pk': self.pk})