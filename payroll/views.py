from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.contrib import messages
from django.shortcuts import get_object_or_404, render, redirect
from django.db.models import Sum
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from employees.models import Employee
from departments.models import Department
from payroll.models import Payroll
from .forms import PayrollForm


ARABIC_MONTHS = [
    (1, 'يناير'), (2, 'فبراير'), (3, 'مارس'), (4, 'أبريل'),
    (5, 'مايو'), (6, 'يونيو'), (7, 'يوليو'), (8, 'أغسطس'),
    (9, 'سبتمبر'), (10, 'أكتوبر'), (11, 'نوفمبر'), (12, 'ديسمبر'),
]


def _filter_value(value):
    """Normalize empty query-string values before applying ORM filters."""
    return value if value and value != 'None' else ''


def _fallback_payroll_row(employee, month, year, status):
    """Build a payroll-shaped row from an active employee's assigned salary."""
    base_salary = employee.salary or Decimal('0')
    return SimpleNamespace(
        pk=None,
        employee=employee,
        month=int(month) if month else None,
        year=int(year) if year else None,
        basic_salary=base_salary,
        allowances=Decimal('0'),
        bonuses=Decimal('0'),
        total_deductions=Decimal('0'),
        net_salary=base_salary,
        status=status or 'PENDING',
        is_fallback=True,
    )


@login_required(login_url='login')
def payroll_dashboard(request):
    department_id = _filter_value(request.GET.get('department'))
    month = _filter_value(request.GET.get('month'))
    year = _filter_value(request.GET.get('year'))
    status = _filter_value(request.GET.get('status'))

    payrolls = Payroll.objects.select_related(
        'employee__user',
        'employee__department',
        'employee__position',
    ).order_by('-year', '-month', '-created_at')

    if department_id:
        payrolls = payrolls.filter(employee__department_id=department_id)
    if month:
        payrolls = payrolls.filter(month=month)
    if year:
        payrolls = payrolls.filter(year=year)

    # Check monthly records before applying status. A status filter can
    # legitimately return zero rows even when the selected month exists.
    has_monthly_payrolls = payrolls.exists() if department_id else True
    if status:
        payrolls = payrolls.filter(status=status)

    # A department can have active employees before its first monthly payroll is
    # created. Use their assigned salaries rather than showing an empty report.
    if department_id and not has_monthly_payrolls and status in ('', 'PENDING'):
        fallback_employees = Employee.objects.select_related(
            'user', 'department', 'position'
        ).filter(
            department_id=department_id,
            user__is_active=True,
        ).order_by('user__first_name', 'user__last_name')
        payrolls = [
            _fallback_payroll_row(employee, month, year, status)
            for employee in fallback_employees
        ]

    if isinstance(payrolls, list):
        total_base = sum((row.basic_salary for row in payrolls), Decimal('0'))
        total_allowances = sum(
            (row.allowances + row.bonuses for row in payrolls), Decimal('0')
        )
        total_deductions = sum(
            (row.total_deductions for row in payrolls), Decimal('0')
        )
        total_net_salary = sum(
            (row.net_salary for row in payrolls), Decimal('0')
        )
        filtered_count = len(payrolls)
        employee_count = len({row.employee.pk for row in payrolls})
    else:
        agg = payrolls.aggregate(
            base=Sum('basic_salary'),
            allowances=Sum('allowances'),
            bonuses=Sum('bonuses'),
            da=Sum('deductions_absence'),
            dd=Sum('deductions_delay'),
            ins=Sum('insurance'),
            od=Sum('other_deductions'),
            net=Sum('net_salary'),
        )
        total_base = agg['base'] or Decimal('0')
        total_allowances = (agg['allowances'] or Decimal('0')) + (agg['bonuses'] or Decimal('0'))
        total_deductions = (
            (agg['da'] or Decimal('0')) + (agg['dd'] or Decimal('0')) +
            (agg['ins'] or Decimal('0')) + (agg['od'] or Decimal('0'))
        )
        total_net_salary = agg['net'] or Decimal('0')
        filtered_count = payrolls.count()
        employee_count = payrolls.values('employee_id').distinct().count()

    years = list(
        Payroll.objects.values_list('year', flat=True).distinct().order_by('-year')
    )
    if year and year.isdigit() and int(year) not in years:
        years.append(int(year))
        years.sort(reverse=True)

    context = {
        'payrolls': payrolls,
        'departments': Department.objects.all().order_by('name'),
        'months': ARABIC_MONTHS,
        'years': years,
        'total_base': total_base,
        'total_allowances': total_allowances,
        'total_deductions': total_deductions,
        'total_net_salary': total_net_salary,
        # Keep the old names available to any consumers outside this template.
        'total_net': total_net_salary,
        'filtered_count': filtered_count,
        'filtered_record_count': filtered_count,
        'processed_count': filtered_count,
        'employee_count': employee_count,
        'selected_department': department_id,
        'selected_month': month,
        'selected_year': year,
        'selected_status': status,
    }
    return render(request, 'payroll/payroll_dashboard.html', context)


@login_required(login_url='login')
def create_payroll(request):
    form = PayrollForm(request.POST or None)
    if form.is_valid():
        payroll = form.save()
        messages.success(request, f'تم إنشاء قسيمة راتب {payroll.employee.get_full_name()} بنجاح.')
        return redirect('payroll_payslip', pk=payroll.pk)
    return render(request, 'payroll/payroll_form.html', {'form': form})


@login_required(login_url='login')
def payroll_payslip(request, pk):
    payroll = get_object_or_404(
        Payroll.objects.select_related('employee__user', 'employee__department', 'employee__position'), pk=pk
    )
    return render(request, 'payroll/payslip.html', {'payroll': payroll})


@login_required(login_url='login')
def export_payroll_pdf(request):
    payrolls = Payroll.objects.select_related('employee__user', 'employee__department', 'employee__position').order_by('-created_at')
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title='Payroll Report')
    styles = getSampleStyleSheet()
    story = [Paragraph('تقرير الرواتب', styles['Title']), Spacer(1, 18)]

    rows = [['الموظف', 'القسم', 'الراتب الأساسي', 'البدلات والمكافآت', 'الخصومات', 'صافي الراتب']]
    for payroll in payrolls:
        total_deductions = payroll.total_deductions
        rows.append([
            payroll.employee.get_full_name() if payroll.employee else 'غير محدد',
            payroll.employee.department.name if payroll.employee and payroll.employee.department else 'غير محدد',
            f'{payroll.basic_salary:.2f}',
            f'{payroll.allowances + payroll.bonuses:.2f}',
            f'{total_deductions:.2f}',
            f'{payroll.net_salary:.2f}',
        ])

    table = Table(rows, colWidths=[140, 90, 70, 70, 70, 70])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d6efd')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
    ]))
    story.append(table)
    doc.build(story)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="payroll_report.pdf"'
    return response
