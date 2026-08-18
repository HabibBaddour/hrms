from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Sum
from django.shortcuts import render

from employees.models import Employee
from leaves.models import LeaveRequest
from payroll.models import Payroll
from performance.models import PerformanceEvaluation


@login_required(login_url='login')
def reports_dashboard(request):
    employee_count = Employee.objects.count()
    leave_count = LeaveRequest.objects.count()
    payroll_total = Payroll.objects.aggregate(total=Sum('net_salary'))['total'] or Decimal('0')
    performance_avg = PerformanceEvaluation.objects.aggregate(avg=Avg('overall_score'))['avg'] or 0

    leave_status_summary = list(
        LeaveRequest.objects.values('status').annotate(total=Count('id')).order_by('-total')
    )

    context = {
        'employee_count': employee_count,
        'leave_count': leave_count,
        'payroll_total': payroll_total,
        'performance_avg': performance_avg,
        'leave_status_summary': leave_status_summary,
        'report_title': 'لوحة التقارير',
    }
    return render(request, 'reports/reports_dashboard.html', context)


@login_required(login_url='login')
def payroll_report(request):
    payrolls = Payroll.objects.select_related('employee__user', 'employee__department', 'employee__position').order_by('-created_at')[:10]
    context = {'payrolls': payrolls, 'report_title': 'تقرير الرواتب'}
    return render(request, 'reports/reports_dashboard.html', context)


@login_required(login_url='login')
def leave_report(request):
    leaves = LeaveRequest.objects.select_related('employee').order_by('-created_at')[:10]
    context = {'leaves': leaves, 'report_title': 'تقرير الإجازات'}
    return render(request, 'reports/reports_dashboard.html', context)


@login_required(login_url='login')
def performance_report(request):
    evaluations = PerformanceEvaluation.objects.select_related('employee__user', 'employee__department', 'employee__position', 'evaluator__user').order_by('-evaluation_date')[:10]
    context = {'evaluations': evaluations, 'report_title': 'تقرير الأداء'}
    return render(request, 'reports/reports_dashboard.html', context)
