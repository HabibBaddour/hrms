"""
Notification utility functions for manual notification creation
"""
from django.contrib.auth.models import User, Group
from .models import SystemNotification


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


def notify_department_created(department, actor=None):
    """Send notification when a new department is created"""
    hr_users = get_hr_users()
    print(f"DEBUG: notify_department_created called for {department.name}, actor: {actor}")
    print(f"DEBUG: HR users count: {hr_users.count()}")
    
    for user in hr_users:
        print(f"DEBUG: Creating notification for user: {user.username}")
        SystemNotification.create_notification(
            recipient=user,
            verb='created',
            notification_type='DEPARTMENT',
            message=f'تم إنشاء قسم جديد: {department.name}',
            actor=actor,
            target=department
        )


def notify_department_updated(department, actor=None):
    """Send notification when a department is updated"""
    hr_users = get_hr_users()
    
    for user in hr_users:
        SystemNotification.create_notification(
            recipient=user,
            verb='updated',
            notification_type='DEPARTMENT',
            message=f'تم تعديل القسم: {department.name}',
            actor=actor,
            target=department
        )


def notify_department_deleted(department_name, actor=None):
    """Send notification when a department is deleted"""
    hr_users = get_hr_users()
    print(f"DEBUG: notify_department_deleted called for {department_name}, actor: {actor}")
    print(f"DEBUG: HR users count: {hr_users.count()}")
    
    for user in hr_users:
        if user != actor:  # Don't notify the user who performed the action
            print(f"DEBUG: Creating delete notification for user: {user.username}")
            SystemNotification.create_notification(
                recipient=user,
                verb='deleted',
                notification_type='DEPARTMENT',
                message=f'تم حذف القسم: {department_name}',
                actor=actor
            )


def notify_position_created(position, actor=None):
    """Send notification when a new position is created"""
    hr_users = get_hr_users()
    
    for user in hr_users:
        SystemNotification.create_notification(
            recipient=user,
            verb='created',
            notification_type='DEPARTMENT',
            message=f'تم إنشاء مسمى وظيفي جديد: {position.title} في قسم {position.department.name}',
            actor=actor,
            target=position
        )


def notify_position_updated(position, actor=None):
    """Send notification when a position is updated"""
    hr_users = get_hr_users()
    
    for user in hr_users:
        SystemNotification.create_notification(
            recipient=user,
            verb='updated',
            notification_type='DEPARTMENT',
            message=f'تم تعديل المسمى الوظيفي: {position.title}',
            actor=actor,
            target=position
        )


def notify_employee_created(employee, actor=None):
    """Send notification when a new employee is created"""
    hr_users = get_hr_users()
    
    for user in hr_users:
        SystemNotification.create_notification(
            recipient=user,
            verb='created',
            notification_type='EMPLOYEE',
            message=f'تم تعيين موظف جديد: {employee.get_full_name()}',
            actor=actor,
            target=employee
        )


def notify_employee_updated(employee, actor=None):
    """Send notification when an employee is updated"""
    hr_users = get_hr_users()
    
    for user in hr_users:
        SystemNotification.create_notification(
            recipient=user,
            verb='updated',
            notification_type='EMPLOYEE',
            message=f'تم تعديل بيانات الموظف: {employee.get_full_name()}',
            actor=actor,
            target=employee
        )


def notify_employee_assigned(employee, actor=None):
    """Send notification when an employee is assigned to a department/position"""
    hr_users = get_hr_users()
    
    for user in hr_users:
        SystemNotification.create_notification(
            recipient=user,
            verb='assigned',
            notification_type='EMPLOYEE',
            message=f'تم تعيين الموظف {employee.get_full_name()} إلى قسم {employee.department.name}',
            actor=actor,
            target=employee
        )


def notify_leave_request(leave_request):
    """Send notification when a leave request is submitted"""
    hr_users = get_hr_users()
    managers = get_managers()
    recipients = (hr_users | managers).distinct()
    
    for user in recipients:
        SystemNotification.create_notification(
            recipient=user,
            verb='submitted',
            notification_type='LEAVE',
            message=f'تم تقديم طلب إجازة جديد من قبل {leave_request.employee.get_full_name()}',
            actor=leave_request.employee.user,
            target=leave_request
        )


def notify_leave_approved(leave_request, actor=None):
    """Send notification when a leave request is approved"""
    SystemNotification.create_notification(
        recipient=leave_request.employee.user,
        verb='approved',
        notification_type='LEAVE',
        message=f'تم الموافقة على طلب إجازتك',
        actor=actor,
        target=leave_request
    )


def notify_leave_rejected(leave_request, actor=None):
    """Send notification when a leave request is rejected"""
    SystemNotification.create_notification(
        recipient=leave_request.employee.user,
        verb='rejected',
        notification_type='LEAVE',
        message=f'تم رفض طلب إجازتك',
        actor=actor,
        target=leave_request
    )