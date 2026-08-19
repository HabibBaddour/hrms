from decimal import Decimal
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.contrib import messages
from django.shortcuts import get_object_or_404, render, redirect
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from employees.models import Employee
from payroll.models import Payroll
from .forms import PayrollForm


@login_required(login_url='login')
def payroll_dashboard(request):
    month = int(request.GET.get('month', 0) or 0)
    year = int(request.GET.get('year', 0) or 0)
    payrolls = Payroll.objects.select_related(
        'employee__user',
        'employee__department',
        'employee__position',
    ).order_by('-year', '-month', '-created_at')
    if month:
        payrolls = payrolls.filter(month=month)
    if year:
        payrolls = payrolls.filter(year=year)

    employees = Employee.objects.select_related('position', 'department', 'user', 'contract').all()
    total_employees = employees.count()

    total_net_salary = sum(
        (
            (
                employee.contract.salary
                if getattr(employee, 'contract', None) and employee.contract.salary is not None
                else employee.position.base_salary
                if employee.position and employee.position.base_salary is not None
                else Decimal('0')
            )
            for employee in employees
        ),
        Decimal('0')
    )

    total_deductions = sum((p.total_deductions for p in payrolls), Decimal('0'))
    processed_count = payrolls.count()

    context = {
        'payrolls': payrolls,
        'total_employees': total_employees,
        'total_net_salary': total_net_salary,
        'total_deductions': total_deductions,
        'processed_count': processed_count,
        'selected_month': f'{month}/{year}' if month and year else 'كل الفترات',
        'month': month,
        'year': year,
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
