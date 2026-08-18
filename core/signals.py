"""
Django signals for automatic notification generation
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User, Group
from django.contrib.contenttypes.models import ContentType

from .models import SystemNotification
from departments.models import Department, Position
from employees.models import Employee
from leaves.models import LeaveRequest


def get_hr_users():
    """Get all HR users and superusers"""
    hr_group = Group.objects.filter(name='HR').first()
    hr_users = User.objects.filter(groups=hr_group) if hr_group else User.objects.none()
    superusers = User.objects.filter(is_superuser=True)
    return (hr_users | superusers).distinct()


def get_managers():
    """Get all managers"""
    manager_group = Group.objects.filter(name='Manager').first()
    if manager_group:
        return User.objects.filter(groups=manager_group)
    return User.objects.none()


# Disable automatic signals to prevent duplicates
# Notifications are now created manually in views to have better control
# @receiver(post_save, sender=Department)
# def notify_department_created(sender, instance, created, **kwargs):
#     """Send notification when a new department is created"""
#     if created:
#         hr_users = get_hr_users()
#         actor = kwargs.get('request_user')
#         
#         for user in hr_users:
#             SystemNotification.create_notification(
#                 recipient=user,
#                 verb='created',
#                 notification_type='DEPARTMENT',
#                 message=f'تم إنشاء قسم جديد: {instance.name}',
#                 actor=actor,
#                 target=instance
#             )

# @receiver(post_save, sender=Position)
# def notify_position_created(sender, instance, created, **kwargs):
#     """Send notification when a new position is created"""
#     if created:
#         hr_users = get_hr_users()
#         actor = kwargs.get('request_user')
#         
#         for user in hr_users:
#             SystemNotification.create_notification(
#                 recipient=user,
#                 verb='created',
#                 notification_type='DEPARTMENT',
#                 message=f'تم إنشاء مسمى وظيفي جديد: {instance.title} في قسم {instance.department.name}',
#                 actor=actor,
#                 target=instance
#             )

# @receiver(post_save, sender=Employee)
# def notify_employee_created(sender, instance, created, **kwargs):
#     """Send notification when a new employee is created"""
#     if created:
#         hr_users = get_hr_users()
#         actor = kwargs.get('request_user')
#         
#         for user in hr_users:
#             SystemNotification.create_notification(
#                 recipient=user,
#                 verb='created',
#                 notification_type='EMPLOYEE',
#                 message=f'تم تعيين موظف جديد: {instance.get_full_name()}',
#                 actor=actor,
#                 target=instance
#             )

# @receiver(post_save, sender=LeaveRequest)
# def notify_leave_request(sender, instance, created, **kwargs):
#     """Send notification when a leave request is submitted"""
#     if created:
#         hr_users = get_hr_users()
#         managers = get_managers()
#         recipients = (hr_users | managers).distinct()
#         
#         for user in recipients:
#             SystemNotification.create_notification(
#                 recipient=user,
#                 verb='submitted',
#                 notification_type='LEAVE',
#                 message=f'تم تقديم طلب إجازة جديد من قبل {instance.employee.get_full_name()}',
#                 actor=instance.employee.user,
#                 target=instance
#             )

# @receiver(post_save, sender=LeaveRequest)
# def notify_leave_status_change(sender, instance, **kwargs):
#     """Send notification when leave request status changes"""
#     if not kwargs.get('created'):
#         # Check if status changed
#         if hasattr(instance, '_original_status') and instance._original_status != instance.status:
#             SystemNotification.create_notification(
#                 recipient=instance.employee.user,
#                 verb='approved' if instance.status == 'approved' else 'rejected',
#                 notification_type='LEAVE',
#                 message=f'تم {"الموافقة على" if instance.status == "approved" else "رفض"} طلب إجازتك',
#                 actor=kwargs.get('request_user'),
#                 target=instance
#             )
