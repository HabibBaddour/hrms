from decimal import Decimal
from io import BytesIO

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


@login_required(login_url='login')
def payroll_dashboard(request):
    department_id = request.GET.get('department')
    month = request.GET.get('month')
    year = request.GET.get('year')
    status = request.GET.get('status')

    payrolls = Payroll.objects.select_related(
        'employee__user',
        'employee__department',
        'employee__position',
    ).order_by('-year', '-month', '-created_at')

    if department_id and department_id != 'None':
        payrolls = payrolls.filter(employee__department_id=department_id)
    if month and month != 'None':
        payrolls = payrolls.filter(month=month)
    if year and year != 'None':
        payrolls = payrolls.filter(year=year)
    if status and status != 'None':
        payrolls = payrolls.filter(status=status)

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
    total_net = agg['net'] or Decimal('0')
    filtered_count = payrolls.count()

    years = list(
        Payroll.objects.values_list('year', flat=True).distinct().order_by('-year')
    )

    context = {
        'payrolls': payrolls,
        'departments': Department.objects.all(),
        'months': ARABIC_MONTHS,
        'years': years,
        'total_base': total_base,
        'total_allowances': total_allowances,
        'total_deductions': total_deductions,
        'total_net': total_net,
        'filtered_count': filtered_count,
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
