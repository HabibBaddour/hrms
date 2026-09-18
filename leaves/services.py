from django.db.models import Max, Q
from django.urls import reverse
from django.utils import timezone

from core.models import InternalMessage, SystemNotification
from employees.models import Employee
from .models import LeaveRequest


def deduplicate_leave_queryset(queryset):
    """Keep the newest row for each logical employee/date/type request."""
    latest_ids = queryset.values(
        'employee_id', 'start_date', 'end_date', 'leave_type'
    ).annotate(latest_id=Max('id')).values('latest_id')
    return queryset.filter(id__in=latest_ids).distinct().order_by('-created_at', '-id')


def get_pending_leaves_count():
    """Return the number of distinct pending requests shown to HR."""
    pending_requests = LeaveRequest.objects.filter(status=LeaveRequest.Status.PENDING)
    return deduplicate_leave_queryset(pending_requests).count()


def _leave_balance(employee):
    total = employee.ANNUAL_LEAVE_DAYS
    approved_requests = employee.leave_requests.filter(
        leave_type='ANNUAL',
        status='APPROVED',
        start_date__year=timezone.localdate().year,
    )
    remaining = employee.get_annual_leave_balance()
    used = sum(request.total_days for request in approved_requests)
    return total, used, remaining


def get_department_manager(department):
    """إرجاع المدير الوحيد للقسم (الحقل الصريح إن وُجد، وإلا دور 'Manager')."""
    if department is None:
        return None
    if getattr(department, 'manager_id', None):
        return department.manager
    return (
        Employee.objects.select_related('user', 'position')
        .filter(
            Q(department_id=department.id) | Q(position__department_id=department.id),
            position__role='Manager',
            user__is_active=True,
        )
        .order_by('id')
        .first()
    )


def notify_leave_submitted(leave, actor=None):
    """Notify the employee's department manager after a leave is successfully created."""
    employee = leave.employee
    actor = actor or getattr(employee, 'user', None)
    employee_name = employee.get_full_name()
    department = employee.department or getattr(employee.position, 'department', None)
    department_name = department.name if department else 'غير محدد'
    job_title = employee.position.title if employee.position else 'غير محدد'
    total, used, remaining = _leave_balance(employee)
    approve_url = reverse('leaves:approve_leave', kwargs={'pk': leave.pk})
    body = (
        f'قام الموظف {employee_name} بتقديم طلب إجازة جديد.\n\n'
        f'بيانات الموظف:\nالاسم: {employee_name}\nالمسمى الوظيفي: {job_title}\nالقسم: {department_name}\n\n'
        f'تفاصيل الإجازة:\nالنوع: {leave.get_leave_type_display()}\n'
        f'من: {leave.start_date}\nإلى: {leave.end_date}\n'
        f'المدة: {leave.total_days} يوم\nالسبب: {leave.reason}\n\n'
        f'رصيد الإجازة السنوي:\nالرصيد الكلي: {total} يوم\n'
        f'الرصيد المستهلك: {used} يوم\nالرصيد المتبقي: {remaining} يوم\n\n'
        f'إجراءات الطلب:\nفتح ومراجعة الطلب: {approve_url}\n'
        f'للقبول أو الرفض، اختر القرار من صفحة المراجعة.'
    )

    manager = get_department_manager(department)
    manager_user = getattr(manager, 'user', None)
    if manager_user and (not actor or manager_user.id != actor.id):
        SystemNotification.create_notification(
            recipient=manager_user,
            actor=actor,
            verb='submitted',
            notification_type='LEAVE',
            message=f'قام الموظف {employee_name} بتقديم طلب إجازة جديد',
            target=leave,
        )
        if actor:
            InternalMessage.objects.create(
                sender=actor,
                recipient=manager_user,
                subject=f'طلب إجازة جديد: {employee_name}',
                body=body,
            )


def notify_leave_status_changed(leave, actor=None):
    employee_user = getattr(leave.employee, 'user', None)
    if not employee_user:
        return
    actor = actor or getattr(leave.approved_by, 'user', None)
    status_label = leave.get_status_display()
    message = f'تم تحديث حالة طلب إجازتك ({leave.get_leave_type_display()}) إلى: {status_label}.'
    SystemNotification.create_notification(
        recipient=employee_user,
        actor=actor,
        verb='approved' if leave.status == 'APPROVED' else 'rejected',
        notification_type='LEAVE',
        message=message,
        target=leave,
    )
