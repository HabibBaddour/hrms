from attendance.models import AttendanceLog
from leaves.models import LeaveRequest


def _normalize_status(value):
    if value is None:
        return ""

    return " ".join(str(value).strip().split())


def build_leave_features(leave_request):
    """
    Build the feature set used by the leave approval model.

    The features are based only on information available
    when the leave request is evaluated.
    """

    employee = leave_request.employee

    # Basic leave information
    duration_days = (
        leave_request.end_date - leave_request.start_date
    ).days + 1

    department_id = str(employee.department_id or "")
    position_id = str(employee.position_id or "")

    # Previous leave history
    previous_requests = LeaveRequest.objects.filter(
        employee=employee,
        created_at__lt=leave_request.created_at,
    )

    previous_approved = previous_requests.filter(
        status="APPROVED"
    ).count()

    previous_rejected = previous_requests.filter(
        status="REJECTED"
    ).count()

    previous_decided = previous_approved + previous_rejected

    if previous_decided > 0:
        approval_rate = previous_approved / previous_decided
    else:
        approval_rate = 0.5

    # Attendance history
    attendance_logs = AttendanceLog.objects.filter(
        employee=employee.user,
        date__lt=leave_request.start_date,
    )

    attendance_total = attendance_logs.count()

    late_count = 0
    on_time_count = 0

    for log in attendance_logs.only("status"):
        status = _normalize_status(log.status)

        if status == "تأخير":
            late_count += 1
        elif status == "حاضر":
            on_time_count += 1

    if attendance_total > 0:
        on_time_rate = on_time_count / attendance_total
    else:
        on_time_rate = 0.5

    # Other leave requests in the same department
    # during the requested period
    overlapping_department_leaves = LeaveRequest.objects.filter(
        employee__department_id=employee.department_id,
        start_date__lte=leave_request.end_date,
        end_date__gte=leave_request.start_date,
        status__in=["APPROVED", "PENDING"],
    ).exclude(
        id=leave_request.id
    )

    same_department_leave_count = (
        overlapping_department_leaves.count()
    )

    return {
        "leave_type": leave_request.leave_type,
        "duration_days": duration_days,
        "department_id": department_id,
        "position_id": position_id,
        "previous_requests": previous_requests.count(),
        "previous_approved": previous_approved,
        "previous_rejected": previous_rejected,
        "approval_rate": approval_rate,
        "on_time_rate": on_time_rate,
        "late_count": late_count,
        "same_department_leave_count": same_department_leave_count,
    }