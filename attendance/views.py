from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import AttendanceLog


@login_required
def attendance_list_view(request):
    attendance_logs = AttendanceLog.objects.filter(employee=request.user).order_by('-date')

    days_present = attendance_logs.filter(status='حاضر').count()

    total_working_hours = 0.0
    for log in attendance_logs:
        if log.check_in and log.check_out:
            delta = log.check_out - log.check_in
            if delta.total_seconds() > 0:
                total_working_hours += delta.total_seconds() / 3600

    context = {
        'attendance_logs': attendance_logs,
        'days_present': days_present,
        'total_working_hours': float(total_working_hours),
    }
    return render(request, 'attendance/attendance_list.html', context)
