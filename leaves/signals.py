from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import LeaveRequest

@receiver(post_save, sender=LeaveRequest)
def update_leave_balance_on_approval(sender, instance, created, **kwargs):
    # الرصيد محسوب من الطلبات المقبولة عبر Employee.get_annual_leave_balance.
    return