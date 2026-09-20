from decimal import Decimal
from datetime import datetime, date, timedelta
from calendar import monthrange
from django.utils import timezone

from attendance.models import AttendanceLog
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
from departments.models import Department, Position
from payroll.models import Payroll
from .forms import PayrollForm, SalaryAdvanceForm

from django.http import HttpResponse, JsonResponse


ARABIC_MONTHS = [
    (1, 'يناير'), (2, 'فبراير'), (3, 'مارس'), (4, 'أبريل'),
    (5, 'مايو'), (6, 'يونيو'), (7, 'يوليو'), (8, 'أغسطس'),
    (9, 'سبتمبر'), (10, 'أكتوبر'), (11, 'نوفمبر'), (12, 'ديسمبر'),
]

def _calculate_attendance_deductions(employee, month, year):
    """
    حساب خصم الغياب والتأخير اعتمادًا على سجلات الحضور الفعلية.

    يوم الجمعة عطلة أسبوعية حسب منطق النظام الحالي.
    بداية الدوام: 08:00
    ساعات العمل اليومية: 8 ساعات
    """

    if not employee or not employee.user_id:
        return Decimal('0.00'), Decimal('0.00')

    try:
        month = int(month)
        year = int(year)
    except (TypeError, ValueError):
        return Decimal('0.00'), Decimal('0.00')

    if not (1 <= month <= 12):
        return Decimal('0.00'), Decimal('0.00')

    first_day = date(year, month, 1)
    last_day = date(
        year,
        month,
        monthrange(year, month)[1],
    )

    # الجمعة عطلة أسبوعية.
    working_days = sum(
        1
        for day_number in range(
            (last_day - first_day).days + 1
        )
        if (
            first_day + timedelta(days=day_number)
        ).weekday() != 4
    )

    if working_days <= 0:
        return Decimal('0.00'), Decimal('0.00')

    logs = AttendanceLog.objects.filter(
        employee_id=employee.user_id,
        date__gte=first_day,
        date__lte=last_day,
    )

    absent_days = 0
    late_minutes = 0

    for log in logs:
        if log.status == AttendanceLog.STATUS_ABSENT:
            absent_days += 1

        elif (
            log.status == AttendanceLog.STATUS_LATE
            and log.check_in
        ):
            check_in_local = timezone.localtime(
                log.check_in
            )

            actual_minutes = (
                check_in_local.hour * 60
                + check_in_local.minute
            )

            start_minutes = 8 * 60

            delay = actual_minutes - start_minutes

            if delay > 0:
                late_minutes += delay

    basic_salary = employee.salary or Decimal('0.00')

    daily_rate = (
        basic_salary / Decimal(working_days)
    )

    absence_deduction = (
        daily_rate * Decimal(absent_days)
    )

    hourly_rate = daily_rate / Decimal('8')

    delay_deduction = (
        hourly_rate
        * Decimal(late_minutes)
        / Decimal('60')
    )

    return (
        absence_deduction.quantize(Decimal('0.01')),
        delay_deduction.quantize(Decimal('0.01')),
    )

@login_required(login_url='login')
def attendance_deductions_api(request):
    employee_id = request.GET.get('employee')
    month = request.GET.get('month')
    year = request.GET.get('year') or datetime.now().year

    if not employee_id or not month:
        return JsonResponse(
            {
                'success': False,
                'message': 'بيانات الموظف أو الشهر ناقصة.'
            },
            status=400,
        )

    try:
        employee = Employee.objects.get(
            pk=employee_id,
            user__is_active=True,
        )

        absence_deduction, delay_deduction = (
            _calculate_attendance_deductions(
                employee,
                int(month),
                int(year),
            )
        )

        return JsonResponse(
            {
                'success': True,
                'absence_deduction': float(absence_deduction),
                'delay_deduction': float(delay_deduction),
                'total_deduction': float(
                    absence_deduction + delay_deduction
                ),
            }
        )

    except Employee.DoesNotExist:
        return JsonResponse(
            {
                'success': False,
                'message': 'الموظف غير موجود.'
            },
            status=404,
        )

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
        overtime_pay=Decimal('0'),
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
    data = request.POST or None
    if data is not None and 'year' not in data:
        data = data.copy()
        data['year'] = datetime.now().year
    form = PayrollForm(data)
    if request.method == 'POST' and form.is_bound:
        existing = Payroll.objects.filter(
            employee_id=request.POST.get('employee'),
            month=request.POST.get('month'),
            year=request.POST.get('year'),
        ).first()
        if existing:
            messages.warning(
                request,
                f'كشف راتب {existing.employee.get_full_name()} عن شهر {existing.month_display} {existing.year} موجود مسبقاً — تم تحويلك إليه.',
            )
            return redirect('payroll_payslip', pk=existing.pk)
        if form.is_valid():
            payroll = form.save(commit=False)

            # حساب خصم الغياب والتأخير من سجلات الحضور الفعلية.
            absence_deduction, delay_deduction = (
                _calculate_attendance_deductions(
                    payroll.employee,
                    payroll.month,
                    payroll.year,
                )
            )

            payroll.deductions_absence = absence_deduction
            payroll.deductions_delay = delay_deduction

            payroll.save()

            messages.success(
                request,
                f'تم إنشاء قسيمة راتب {payroll.employee.get_full_name()} '
                f'مع احتساب خصم الغياب والتأخير تلقائياً.'
            )

            return redirect(
                'payroll_payslip',
                pk=payroll.pk,
            )
    context = {
        'form': form,
        'employee_options': form.fields['employee'].queryset,
        'departments': Department.objects.all().order_by('name'),
        'roles': list(
            Position.objects.exclude(role='').values_list('role', flat=True).distinct().order_by('role')
        ),
    }
    return render(request, 'payroll/payroll_form.html', context)


@login_required(login_url='login')
def payroll_payslip(request, pk):
    payroll = get_object_or_404(
        Payroll.objects.select_related('employee__user', 'employee__department', 'employee__position'), pk=pk
    )

    ar_months = ['كانون الثاني', 'شباط', 'آذار', 'نيسان', 'أيار', 'حزيران',
                 'تموز', 'آب', 'أيلول', 'تشرين الأول', 'تشرين الثاني', 'كانون الأول']
    month_name = ar_months[payroll.month - 1] if 1 <= payroll.month <= 12 else str(payroll.month)

    gross = float(payroll.gross_salary)
    deductions = float(payroll.total_deductions)
    net = float(payroll.net_salary)
    safe_gross = gross if gross > 0 else 1.0

    earnings = [
        {'label': 'الراتب الأساسي', 'icon': 'fa-sack-dollar', 'value': float(payroll.basic_salary)},
        {'label': 'البدلات', 'icon': 'fa-hand-holding-dollar', 'value': float(payroll.allowances)},
        {'label': 'المكافآت', 'icon': 'fa-gift', 'value': float(payroll.bonuses)},
        {'label': 'أجر العمل الإضافي', 'icon': 'fa-clock', 'value': float(payroll.overtime_pay)},
    ]
    tones = ['emerald', 'teal', 'gold', 'sky']
    for idx, item in enumerate(earnings):
        item['pct'] = round(item['value'] / safe_gross * 100)
        item['tone'] = tones[idx]

    payment_details = {
        'method_display': payroll.get_payment_method_display(),
        'bank_name': payroll.bank_name.strip() if payroll.bank_name else '',
        'account_number': payroll.account_number.strip() if payroll.account_number else '',
    }

    deduction_items = [
        {'label': 'خصم الغياب', 'icon': 'fa-user-slash', 'value': float(payroll.deductions_absence)},
        {'label': 'خصم التأخير', 'icon': 'fa-clock', 'value': float(payroll.deductions_delay)},
        {'label': 'التأمينات', 'icon': 'fa-shield-halved', 'value': float(payroll.insurance)},
        {'label': 'خصومات أخرى', 'icon': 'fa-ellipsis', 'value': float(payroll.other_deductions)},
    ]

    prev_month = payroll.month - 1 or 12
    prev_year = payroll.year if payroll.month > 1 else payroll.year - 1
    previous = Payroll.objects.filter(
        employee=payroll.employee, month=prev_month, year=prev_year,
    ).first()
    comparison = None
    if previous:
        diff = net - float(previous.net_salary)
        prev_net = float(previous.net_salary)
        pct = round(abs(diff) / prev_net * 100) if prev_net > 0 else 0
        comparison = {
            'month_name': ar_months[prev_month - 1],
            'net': prev_net,
            'diff': diff,
            'pct': pct,
            'direction': 'up' if diff > 0 else ('down' if diff < 0 else 'same'),
        }

    context = {
        'payroll': payroll,
        'month_name': month_name,
        'gross': gross,
        'deductions_total': deductions,
        'net': net,
        'earnings': earnings,
        'deduction_items': deduction_items,
        'payment_details': payment_details,
        'comparison': comparison,
    }
    return render(request, 'payroll/payslip.html', context)


@login_required(login_url='login')
def my_payslips(request):
    """Employee-facing list of their own payslips."""
    employee = getattr(request.user, 'employee_profile', None)
    payslips = Payroll.objects.none()
    if employee:
        payslips = Payroll.objects.filter(employee=employee).order_by('-year', '-month')

    month_map = {num: name for num, name in ARABIC_MONTHS}
    for p in payslips:
        p.month_name = month_map.get(p.month, str(p.month))

    total_net = sum(float(p.net_salary) for p in payslips)
    paid_net = sum(float(p.net_salary) for p in payslips if p.status == 'PAID')

    context = {
        'employee': employee,
        'payslips': payslips,
        'count': payslips.count(),
        'total_net': total_net,
        'paid_net': paid_net,
        'months': ARABIC_MONTHS,
    }
    return render(request, 'payroll/my_payslips.html', context)


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


@login_required(login_url='login')
def salary_advance_apply(request):
    """استقبال طلب سلفة مالية عبر POST ثم إعادة التوجيه لصفحة القسائم."""
    if request.method != 'POST':
        return redirect('my_payslips')

    employee = getattr(request.user, 'employee_profile', None)
    if employee is None:
        messages.error(request, 'تعذر العثور على ملفك الوظيفي. تواصل مع الإدارة.')
        return redirect('employees:payslip_list')

    form = SalaryAdvanceForm(request.POST)
    if form.is_valid():
        advance = form.save(commit=False)
        advance.employee = employee
        advance.save()
        messages.success(
            request,
            f'تم إرسال طلب السلفة بمبلغ {advance.amount} $ لفترة {advance.months} شهر بنجاح.',
        )
    else:
        messages.error(request, 'تأكد من صحة البيانات المدخلة ثم أعد المحاولة.')

    return redirect('employees:payslip_list')
