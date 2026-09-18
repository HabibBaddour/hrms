import csv
from calendar import monthrange
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.html import escape

from departments.models import Department
from employees.models import Employee
from leaves.models import LeaveRequest
from leaves.views import _apply_leave_context, _leave_list_context

from .models import AttendanceLog, format_duration_text

ARABIC_MONTHS = [
    'يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
    'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر',
]

STATUS_LABELS = {
    AttendanceLog.STATUS_PRESENT: 'حاضر',
    AttendanceLog.STATUS_LATE: 'متأخر',
    AttendanceLog.STATUS_ABSENT: 'غائب',
}

LEAVE_EVENT_COLORS = {
    LeaveRequest.LeaveType.ANNUAL: '#f59e0b',
    LeaveRequest.LeaveType.EMERGENCY: '#f97316',
    LeaveRequest.LeaveType.SICK: '#8b5cf6',
    LeaveRequest.LeaveType.UNPAID: '#64748b',
}

ARABIC_WEEKDAYS = {
    0: 'الإثنين',
    1: 'الثلاثاء',
    2: 'الأربعاء',
    3: 'الخميس',
    4: 'الجمعة',
    5: 'السبت',
    6: 'الأحد',
}


def _arabic_day_name(date_value):
    return ARABIC_WEEKDAYS.get(date_value.weekday(), 'غير معروف')


def _format_calendar_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value).split('T')[0])
    except (TypeError, ValueError):
        return None


def _format_time(value, fallback='--:--'):
    return value.strftime('%I:%M %p') if value else fallback


def _resolve_user_role(user):
    """Mirror core.context_processors: HR (staff/superuser/HR Admin role),
    Manager (position role), otherwise Employee."""
    if user.is_superuser or user.is_staff:
        return 'HR'
    profile = getattr(user, 'employee_profile', None)
    position = getattr(profile, 'position', None) if profile else None
    role = (position.role or '').lower() if position else ''
    if role == 'manager':
        return 'MANAGER'
    if role in ('hr', 'hr admin', 'hr_admin'):
        return 'HR'
    return 'EMPLOYEE'


def _month_bounds(year, month):
    start = date(year, month, 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    return start, date(next_year, next_month, 1)


@login_required
def attendance_list_view(request):
    today = timezone.localdate()
    selected_year = request.GET.get('year', today.year)
    selected_month = request.GET.get('month', today.month)

    try:
        display_year = int(selected_year)
    except (TypeError, ValueError):
        display_year = today.year
    if not 1 <= display_year <= 9999:
        display_year = today.year
    try:
        display_month = int(selected_month)
    except (TypeError, ValueError):
        display_month = today.month
    if not 1 <= display_month <= 12:
        display_month = today.month

    selected_year = display_year
    selected_month = display_month
    attendance_logs = AttendanceLog.objects.filter(
        employee=request.user,
        date__year=display_year,
        date__month=display_month,
    ).order_by('-date', '-check_in')

    export = request.GET.get('export')
    if export == 'excel':
        return _export_attendance_excel(attendance_logs)
    if export == 'pdf':
        return _export_attendance_pdf(attendance_logs)

    last_day_number = monthrange(display_year, display_month)[1]
    logs_by_date = {log.date: log for log in attendance_logs}

    month_logs = [
        log for day, log in logs_by_date.items()
        if day.year == display_year and day.month == display_month
    ]
    days_present = sum(1 for log in month_logs if log.status == AttendanceLog.STATUS_PRESENT)
    days_late = sum(1 for log in month_logs if log.status == AttendanceLog.STATUS_LATE)
    days_absent = sum(1 for log in month_logs if log.status == AttendanceLog.STATUS_ABSENT)

    total_seconds = 0.0
    for log in month_logs:
        if log.check_in and log.check_out:
            delta = log.check_out - log.check_in
            if delta.total_seconds() > 0:
                total_seconds += delta.total_seconds()

    attendance_rows = []
    for day_number in range(1, last_day_number + 1):
        row_date = date(display_year, display_month, day_number)
        log = logs_by_date.get(row_date)
        attendance_rows.append({
            'date': row_date,
            'day_name': _arabic_day_name(row_date),
            'is_today': row_date == today,
            'is_future': row_date > today,
            'is_friday': row_date.weekday() == 4,
            'check_in': log.check_in if log else None,
            'check_out': log.check_out if log else None,
            'status': log.status if log else None,
            'working_hours_readable': log.working_hours_readable if log else None,
        })

    this_year = timezone.now().year
    employee_profile = getattr(request.user, 'employee_profile', None)
    current_department = getattr(employee_profile, 'department', None) if employee_profile else None

    hire_year = None
    if employee_profile:
        contract = getattr(employee_profile, 'contract', None)
        if contract and contract.start_date:
            hire_year = contract.start_date.year
    if hire_year and hire_year <= this_year:
        year_options = [year_value for year_value in range(this_year, hire_year - 1, -1)]
    else:
        year_options = [this_year]
    year_options = sorted(set(year_options) | {display_year}, reverse=True)

    context = {
        'attendance_rows': attendance_rows,
        'personal_attendance_rows': attendance_rows,
        'attendance_logs': attendance_logs,
        'days_present': days_present,
        'days_late': days_late,
        'days_absent': days_absent,
        'total_working_hours_text': format_duration_text(total_seconds),
        'display_month': display_month,
        'display_year': display_year,
        'today': today,
        'selected_month': selected_month,
        'selected_year': selected_year,
        'months_list': [(number, ARABIC_MONTHS[number - 1]) for number in range(1, 13)],
        'month_options': [(number, ARABIC_MONTHS[number - 1]) for number in range(1, 13)],
        'available_years': year_options,
        'year_options': year_options,
        'current_department_name': getattr(current_department, 'name', ''),
        'today_iso': today.isoformat(),
        'view_role': _resolve_user_role(request.user),
    }

    if context['view_role'] == 'HR':
        context.update(_hr_analytics_context())
    elif context['view_role'] == 'MANAGER':
        context.update(_manager_dashboard_context(request.user, display_year, display_month))

    # بيانات تبويب "الإجازات" المدمج في نفس الصفحة
    context.update(_leave_list_context(request))
    context.update(_apply_leave_context(request))
    
    # Handle active tab for Manager (personal, team, leaves) and Employee (personal, leaves)
    tab_param = request.GET.get('tab')
    if context['view_role'] == 'MANAGER':
        if tab_param == 'team':
            context['active_tab'] = 'team'
        elif tab_param == 'leaves':
            context['active_tab'] = 'leaves'
        else:
            context['active_tab'] = 'personal'
    else:
        context['active_tab'] = 'leaves' if tab_param == 'leaves' else 'personal'

    return render(request, 'attendance/attendance_list.html', context)


def _hr_analytics_context():
    """Department attendance rates + approved leave distribution."""
    today = timezone.localdate()
    month_start = today.replace(day=1)

    dept_names = []
    dept_rates = []
    for dept in Department.objects.all().order_by('name'):
        dept_logs = AttendanceLog.objects.filter(
            employee__employee_profile__department=dept,
            date__gte=month_start,
        )
        total = dept_logs.count()
        present = dept_logs.filter(status=AttendanceLog.STATUS_PRESENT).count()
        dept_names.append(dept.name)
        dept_rates.append(round(present / total * 100, 1) if total else 0)

    leave_counts = {leave_type: 0 for leave_type in LeaveRequest.LeaveType.values}
    for leave_type, count_value in (
        LeaveRequest.objects.filter(status=LeaveRequest.Status.APPROVED)
        .values_list('leave_type')
        .annotate(total_count=Count('id'))
        .order_by()
    ):
        leave_counts[leave_type] = count_value

    today_logs = AttendanceLog.objects.filter(date=today)
    return {
        'dept_names': dept_names,
        'dept_rates': dept_rates,
        'leave_labels': [LeaveRequest.LeaveType(item).label for item in LeaveRequest.LeaveType.values],
        'leave_values': [leave_counts[item] for item in LeaveRequest.LeaveType.values],
        'today_present': today_logs.filter(status=AttendanceLog.STATUS_PRESENT).count(),
        'today_total': today_logs.count(),
        'dept_count': len(dept_names),
    }


def _team_month_aggregates(user, month_start, month_next_start):
    """Per-day attendance + approved leave counts for the user's department."""
    profile = getattr(user, 'employee_profile', None)
    dept = getattr(profile, 'department', None) if profile else None
    if dept is None:
        return '', []

    members = list(Employee.objects.filter(department=dept).select_related('user'))
    member_ids = [member.id for member in members]
    team_total = len(members)

    def empty_day():
        return {'present': 0, 'late': 0, 'absent': 0, 'leave': 0, 'absent_employees': []}

    aggregates = {}
    logs_by_day = {}

    logs = AttendanceLog.objects.filter(
        employee__employee_profile__department=dept,
        date__gte=month_start,
        date__lt=month_next_start,
    ).select_related('employee')
    for log in logs:
        day_key = log.date.isoformat()
        day = aggregates.setdefault(day_key, empty_day())
        logs_by_day.setdefault(day_key, set()).add(log.employee_id)
        if log.status == AttendanceLog.STATUS_LATE:
            day['late'] += 1
        elif log.status == AttendanceLog.STATUS_ABSENT:
            day['absent'] += 1
            employee_name = log.employee.get_full_name() or log.employee.username
            if employee_name not in day['absent_employees']:
                day['absent_employees'].append(employee_name)
        else:
            day['present'] += 1

    leaves = LeaveRequest.objects.filter(
        employee__in=member_ids,
        status=LeaveRequest.Status.APPROVED,
        end_date__gte=month_start,
        start_date__lt=month_next_start,
    ).select_related('employee')
    for leave in leaves:
        day_iter = max(leave.start_date, month_start)
        last_day = min(leave.end_date, month_next_start - timedelta(days=1))
        while day_iter <= last_day:
            day_key = day_iter.isoformat()
            day = aggregates.setdefault(day_key, empty_day())
            day['leave'] += 1
            day_iter += timedelta(days=1)

    today = timezone.localdate()
    leave_members_by_day = {}
    for leave in leaves:
        day_iter = max(leave.start_date, month_start)
        last_day = min(leave.end_date, month_next_start - timedelta(days=1))
        while day_iter <= last_day:
            leave_members_by_day.setdefault(day_iter.isoformat(), set()).add(leave.employee_id)
            day_iter += timedelta(days=1)

    result = []
    for key in sorted(aggregates):
        value = aggregates[key]
        current_day = date.fromisoformat(key)
        if current_day < today and current_day.weekday() != 4:
            logged_members = logs_by_day.get(key, set())
            leave_members = leave_members_by_day.get(key, set())
            for member in members:
                if member.user_id not in logged_members and member.id not in leave_members:
                    value['absent_employees'].append(member.get_full_name())
            value['absent_employees'] = sorted(set(value['absent_employees']))
            value['absent'] = len(value['absent_employees'])

        total = max(team_total, 1)
        present_count = value['present']
        daily_pct = round((present_count / total) * 100) if total else 0
        result.append({
            'date': key,
            'present': present_count,
            'present_count': present_count,
            'late': value['late'],
            'absent': value['absent'],
            'leave': value['leave'],
            'daily_pct': daily_pct,
            'attendance_percentage': float(daily_pct),
            'total_team_count': total,
            'absent_employees': value['absent_employees'],
        })

    return dept.name, result


def _manager_dashboard_context(user, display_year, display_month):
    month_start, month_next_start = _month_bounds(display_year, display_month)
    dept_name, daily = _team_month_aggregates(user, month_start, month_next_start)
    profile = getattr(user, 'employee_profile', None)
    dept = getattr(profile, 'department', None) if profile else None
    total_team_count = Employee.objects.filter(department=dept).count() if dept else 0

    return {
        'department_name': dept_name,
        'team_members_count': total_team_count,
        'total_team_count': total_team_count,
        'team_month_data': daily,
        'manager_month': f'{display_year:04d}-{display_month:02d}',
    }


@login_required
def team_month_api(request):
    """Per-day department attendance/leave aggregates for the navigation JS."""
    role = _resolve_user_role(request.user)
    if role == 'EMPLOYEE':
        return JsonResponse({'error': 'غير مصرح'}, status=403)

    month_str = request.GET.get('month', '')
    try:
        year, month = (int(part) for part in month_str.split('-'))
    except (TypeError, ValueError):
        year, month = timezone.localdate().year, timezone.localdate().month
    try:
        month_start, month_next_start = _month_bounds(year, month)
    except ValueError:
        month_start, month_next_start = _month_bounds(
            timezone.localdate().year, timezone.localdate().month)
    dept_name, daily = _team_month_aggregates(request.user, month_start, month_next_start)
    return JsonResponse({
        'department': dept_name,
        'month': f'{year:04d}-{month:02d}',
        'data': daily,
    })


@login_required
def attendance_calendar_events(request):
    """JSON endpoint feeding the FullCalendar schedule (current user only)."""
    start = _format_calendar_date(request.GET.get('start'))
    end = _format_calendar_date(request.GET.get('end'))
    if start is None or end is None:
        return JsonResponse([], safe=False)

    events = []
    today = timezone.localdate()
    covered = set()

    logs = AttendanceLog.objects.filter(
        employee=request.user,
        date__gte=start,
        date__lte=end,
    ).order_by('date')
    for log in logs:
        covered.add(log.date)
        if log.status == AttendanceLog.STATUS_LATE:
            title = f"متأخر - {_format_time(log.check_in)}" if log.check_in else 'متأخر'
            color = '#ef4444'
        elif log.status == AttendanceLog.STATUS_PRESENT:
            title = f"حاضر - {_format_time(log.check_in)}" if log.check_in else 'حاضر'
            color = '#16a34a'
        else:
            title = 'غائب'
            color = '#dc2626'
        events.append({
            'id': f'att-{log.id}',
            'title': title,
            'start': log.date.isoformat(),
            'allDay': True,
            'color': color,
            'classNames': ['att-event'],
        })

    leaves = LeaveRequest.objects.filter(
        employee__user=request.user,
        status=LeaveRequest.Status.APPROVED,
        end_date__gte=start,
        start_date__lte=end,
    )
    for leave in leaves:
        leave_day = leave.start_date
        while leave_day <= leave.end_date:
            covered.add(leave_day)
            leave_day += timedelta(days=1)
        events.append({
            'id': f'leave-{leave.id}',
            'title': leave.get_leave_type_display(),
            'start': leave.start_date.isoformat(),
            'end': (leave.end_date + timedelta(days=1)).isoformat(),
            'allDay': True,
            'color': LEAVE_EVENT_COLORS.get(leave.leave_type, '#f59e0b'),
            'classNames': ['att-event', 'att-leave'],
            'extendedProps': {
                'leaveType': leave.get_leave_type_display(),
                'statusTxt': leave.get_status_display(),
            },
        })

    absent_day = start
    while absent_day <= end:
        if (
            absent_day < today
            and absent_day.weekday() != 4
            and absent_day not in covered
        ):
            events.append({
                'id': f'absent-{absent_day.isoformat()}',
                'title': 'غائب',
                'start': absent_day.isoformat(),
                'allDay': True,
                'color': '#dc2626',
                'classNames': ['att-event', 'att-absent'],
            })
        absent_day += timedelta(days=1)

    return JsonResponse(events, safe=False)


@login_required
def day_details_api(request):
    """Roster of the current user's department for a single date, or a single employee cell."""
    date_str = request.GET.get('date', '')
    employee_id = request.GET.get('employee_id')
    try:
        selected_date = date.fromisoformat(date_str)
    except (TypeError, ValueError):
        return JsonResponse({'error': 'تاريخ غير صالح', 'roster': []})

    employee_profile = getattr(request.user, 'employee_profile', None)
    department = getattr(employee_profile, 'department', None) if employee_profile else None
    if department is None:
        return JsonResponse({
            'date': date_str,
            'day_name': _arabic_day_name(selected_date),
            'department': '',
            'roster': [],
        })

    members = list(
        Employee.objects.filter(department=department)
        .select_related('user', 'position')
        .order_by('id')
    )
    if employee_id:
        members = [member for member in members if str(member.id) == str(employee_id)]

    user_ids = {member.user_id for member in members if member.user_id}
    logs = {
        log.employee_id: log
        for log in AttendanceLog.objects.filter(
            employee_id__in=user_ids, date=selected_date
        )
    }
    leaves = {
        leave.employee_id: leave
        for leave in LeaveRequest.objects.filter(
            employee__department=department,
            status=LeaveRequest.Status.APPROVED,
            start_date__lte=selected_date,
            end_date__gte=selected_date,
        ).select_related('employee')
    }

    today = timezone.localdate()
    friday = selected_date.weekday() == 4
    roster = []
    for member in members:
        log = logs.get(member.user_id)
        leave = leaves.get(member.id)
        row = {
            'id': member.id,
            'name': member.get_full_name(),
            'position': member.position.title if member.position_id else '',
            'avatar_url': member.get_profile_picture_url(),
            'first_letter': (member.get_full_name() or '#')[:1],
            'check_in': '--:--',
            'check_out': '--:--',
            'hours': 0,
        }
        if leave:
            row.update(
                status='LEAVE',
                status_label='في إجازة',
                leave_type=leave.get_leave_type_display(),
                leave_status=leave.get_status_display(),
            )
        elif log:
            row.update(
                status='LATE'
                if log.status == AttendanceLog.STATUS_LATE
                else 'PRESENT',
                status_label=STATUS_LABELS.get(log.status, log.status),
                check_in=_format_time(log.check_in),
                check_out=_format_time(log.check_out),
                hours=log.get_working_hours(),
            )
        else:
            absent = (not friday) and selected_date < today
            row.update(
                status='ABSENT' if absent else 'NONE',
                status_label=('غائب' if absent else ('عطلة أسبوعية' if friday else '—')),
            )
        roster.append(row)

    return JsonResponse({
        'date': selected_date.isoformat(),
        'day_name': _arabic_day_name(selected_date),
        'department': getattr(department, 'name', ''),
        'roster': roster,
    })


def _export_attendance_excel(attendance_logs):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="attendance_log.csv"'
    # UTF-8 BOM so Excel renders Arabic labels correctly.
    response.write('\ufeff')
    writer = csv.writer(response, dialect=csv.excel, lineterminator='\n')
    writer.writerow([
        'اسم اليوم', 'التاريخ', 'توقيت الدخول', 'توقيت الخروج',
        'إجمالي ساعات العمل', 'الحالة',
    ])
    for log in attendance_logs:
        writer.writerow([
            log.day_name,
            log.date.isoformat(),
            log.check_in.strftime('%H:%M') if log.check_in else '--:--',
            log.check_out.strftime('%H:%M') if log.check_out else '--:--',
            f'{log.get_working_hours()} ساعة',
            STATUS_LABELS.get(log.status, log.status),
        ])
    return response


def _export_attendance_pdf(attendance_logs):
    from weasyprint import HTML

    rows_html = ''
    for log in attendance_logs:
        rows_html += (
            '<tr>'
            f'<td>{escape(log.day_name)}</td>'
            f'<td>{log.date.isoformat()}</td>'
            f'<td>{log.check_in.strftime("%H:%M") if log.check_in else "--:--"}</td>'
            f'<td>{log.check_out.strftime("%H:%M") if log.check_out else "--:--"}</td>'
            f'<td>{log.get_working_hours()} ساعة</td>'
            f'<td>{escape(STATUS_LABELS.get(log.status, log.status))}</td>'
            '</tr>'
        )

    html = f'''<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<style>
    * {{ font-family: "Segoe UI", Tahoma, sans-serif; }}
    body {{ padding: 18px; color: #1e293b; }}
    h2 {{ margin: 0 0 4px; }}
    .sub {{ color: #64748b; font-size: 12px; margin-bottom: 16px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 11px; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 7px 8px; text-align: center; }}
    th {{ background: #f1f5f9; font-weight: 700; }}
    td.time {{ font-family: Consolas, monospace; direction: ltr; }}
</style>
</head>
<body>
<h2>جدول الدوام والإجازات</h2>
<div class="sub">سجل حضور الموظف - عدد السجلات: {attendance_logs.count()}</div>
<table>
<thead>
<tr>
<th>اسم اليوم</th><th>التاريخ</th><th>توقيت الدخول</th>
<th>توقيت الخروج</th><th>إجمالي ساعات العمل</th><th>الحالة</th>
</tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>
</body>
</html>'''

    response = HttpResponse(HTML(string=html).write_pdf(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="attendance_report.pdf"'
    return response