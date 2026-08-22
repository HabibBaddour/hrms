from django.db import models
from django.contrib.auth.models import Group

class Department(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="اسم القسم")
    code = models.CharField(max_length=10, unique=True, verbose_name="رمز القسم")
    description = models.TextField(blank=True, null=True, verbose_name="وصف القسم")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "قسم"
        verbose_name_plural = "الأقسام"

    def __str__(self):
        return self.name


class Position(models.Model):
    ROLE_CHOICES = [
        ('Employee', 'موظف'),
        ('Manager', 'مدير'),
        ('HR Admin', 'مسؤول موارد بشرية'),
    ]
    
    title = models.CharField(max_length=100, verbose_name="المسمى الوظيفي")
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='positions', verbose_name="القسم")
    base_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="الراتب التقديري")
    salary_min = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="الحد الأدنى للراتب")
    salary_max = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="الحد الأقصى للراتب")
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="الدور والصلاحية")
    role = models.CharField(max_length=100, choices=ROLE_CHOICES, default='Employee', verbose_name="الدور")
    is_head = models.BooleanField(default=False, verbose_name="رئيس القسم")

    class Meta:
        verbose_name = "وظيفة"
        verbose_name_plural = "الوظائف"

    def __str__(self):
        return f"{self.title} - ({self.department.name})"