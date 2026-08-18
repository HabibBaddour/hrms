from django.db import models
from django.contrib.auth.models import User
from departments.models import Department, Position
from django.utils import timezone

class Employee(models.Model):
    ANNUAL_LEAVE_DAYS = 15

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_profile', null=True, blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    position = models.ForeignKey(Position, on_delete=models.SET_NULL, null=True, blank=True)
    first_name = models.CharField(max_length=100, null=True, blank=True)
    last_name = models.CharField(max_length=100, null=True, blank=True)
    national_id = models.CharField(max_length=50, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    temporary_password = models.CharField(max_length=100, null=True, blank=True, help_text="كلمة المرور المؤقتة للاستخدام الداخلي فقط")
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True, verbose_name="صورة الملف الشخصي")
    date_of_birth = models.DateField(null=True, blank=True, verbose_name="تاريخ الميلاد")
    address = models.TextField(null=True, blank=True, verbose_name="العنوان")
    emergency_contact = models.CharField(max_length=100, null=True, blank=True, verbose_name="جهة الاتصال الطارئة")
    emergency_phone = models.CharField(max_length=20, null=True, blank=True, verbose_name="رقم هاتف الطوارئ")

    def __str__(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.user:
            return f"{self.user.first_name} {self.user.last_name}"
        return f"Employee #{self.id}"
    
    def get_full_name(self):
        """Get the full name from User model or Employee model"""
        if self.user and (self.user.first_name or self.user.last_name):
            return f"{self.user.first_name} {self.user.last_name}".strip()
        elif self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return f"Employee #{self.id}"

    def get_annual_leave_balance(self, year=None):
        year = year or timezone.localdate().year
        approved_days = sum(
            leave.total_days
            for leave in self.leave_requests.filter(
                leave_type='ANNUAL',
                status='APPROVED',
                start_date__year=year,
            )
        )
        return max(self.ANNUAL_LEAVE_DAYS - approved_days, 0)
    
    def get_profile_picture_url(self):
        """Get profile picture URL or return default avatar"""
        if self.profile_picture:
            return self.profile_picture.url
        return None


class EmployeePhone(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='phone_numbers')
    number = models.CharField(max_length=20, verbose_name='رقم الهاتف')
    label = models.CharField(max_length=50, default='Mobile', blank=True, verbose_name='التسمية')
    is_primary = models.BooleanField(default=False, verbose_name='رقم رئيسي')

    class Meta:
        ordering = ['-is_primary', 'id']
        unique_together = ('employee', 'number')

    def __str__(self):
        return f"{self.employee} - {self.number}"


class Contract(models.Model):
    CONTRACT_TYPES = (
        ('Full-Time', 'دوام كامل'),
        ('Part-Time', 'دوام جزئي'),
        ('Fixed-Term', 'عقد محدد المدة'),
        ('Internship', 'تدريب'),
    )
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name='contract')
    contract_type = models.CharField(max_length=20, choices=CONTRACT_TYPES, default='Full-Time')
    salary = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"عقد الموظف {self.employee}"