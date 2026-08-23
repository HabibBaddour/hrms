from django.db import models
from django.contrib.auth.models import Group
from django.db.models.signals import post_save
from django.dispatch import receiver

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

    @property
    def estimated_salary(self):
        return round(float(self.base_salary or 0), 2)

    def __str__(self):
        return f"{self.title} - ({self.department.name})"


@receiver(post_save, sender=Position)
def sync_position_employees_salary(sender, instance, **kwargs):
    """When a position's salary is changed, automatically update all of its employees."""
    from employees.models import Employee, Contract
    estimated = instance.estimated_salary
    Employee.objects.filter(position=instance).update(salary=estimated)
    Contract.objects.filter(employee__position=instance).update(salary=estimated)