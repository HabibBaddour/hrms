"""
Context processors for notifications
"""
from .models import SystemNotification


def notifications_context(request):
    """Inject notification data into all templates"""
    unread_count = 0
    recent_notifications = []
    user_role = 'Employee'
    
    try:
        if request.user and request.user.is_authenticated:
            unread_count = SystemNotification.get_unread_count(request.user)
            recent_notifications = SystemNotification.get_recent_notifications(request.user, limit=5)
            
            # Determine user role from employee profile
            try:
                employee = request.user.employee_profile
                if employee.position:
                    user_role = employee.position.role
            except:
                user_role = 'Employee'
    except Exception as e:
        # Log error if needed
        pass
    
    return {
        'unread_notifications_count': unread_count,
        'recent_notifications': recent_notifications,
        'user_role': user_role,
    }