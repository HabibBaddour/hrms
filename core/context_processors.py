"""
Context processors for notifications
"""
from .models import SystemNotification


def notifications_context(request):
    """Inject notification data into all templates"""
    unread_count = 0
    recent_notifications = []
    user_role = 'Employee'
    latest_payslip_id = None

    try:
        if request.user and request.user.is_authenticated:
            unread_count = SystemNotification.get_unread_count(request.user)
            recent_notifications = SystemNotification.get_recent_notifications(request.user, limit=5)

            # Determine user role from employee profile
            try:
                employee = request.user.employee_profile
                if employee.position:
                    user_role = employee.position.role

                from payroll.models import Payroll
                latest = Payroll.objects.filter(
                    employee=employee,
                ).order_by('-year', '-month').values_list('pk', flat=True).first()
                if latest:
                    latest_payslip_id = latest
            except Exception:
                pass
    except Exception:
        # Log error if needed
        pass

    return {
        'unread_notifications_count': unread_count,
        'recent_notifications': recent_notifications,
        'user_role': user_role,
        'latest_payslip_id': latest_payslip_id,
    }