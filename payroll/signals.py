from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Payroll


@receiver(post_save, sender=Payroll)
def sync_payslip_on_save(sender, instance, **kwargs):
    instance.sync_payslip()


@receiver(post_delete, sender=Payroll)
def delete_payslip_on_delete(sender, instance, **kwargs):
    from employees.models import Payslip
    Payslip.objects.filter(employee=instance.employee, month=instance.month, year=instance.year).delete()