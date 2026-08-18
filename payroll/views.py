from decimal import Decimal
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from employees.models import Employee
from payroll.models import Payroll


@login_required(login_url='login')
def payroll_dashboard(request):
    payrolls = Payroll.objects.select_related(
        'employee__user',
        'employee__department',
        'employee__position',
    ).order_by('-created_at')[:10]

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

    total_deductions = sum(
        (
            p.deductions_absence + p.deductions_delay + p.insurance + p.other_deductions
            for p in Payroll.objects.all()
        ),
        Decimal('0')
    )
    processed_count = employees.filter(
        position__isnull=False
    ).count()

    context = {
        'payrolls': payrolls,
        'total_employees': total_employees,
        'total_net_salary': total_net_salary,
        'total_deductions': total_deductions,
        'processed_count': processed_count,
        'selected_month': 'شهر الحالي',
    }
    return render(request, 'payroll/payroll_dashboard.html', context)


@login_required(login_url='login')
def export_payroll_pdf(request):
    payrolls = Payroll.objects.select_related('employee__user', 'employee__department', 'employee__position').order_by('-created_at')
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title='Payroll Report')
    styles = getSampleStyleSheet()
    story = [Paragraph('تقرير الرواتب', styles['Title']), Spacer(1, 18)]

    rows = [['الموظف', 'القسم', 'الراتب الأساسي', 'البدلات', 'الخصومات', 'صافي الراتب']]
    for payroll in payrolls:
        total_deductions = (
            payroll.deductions_absence + payroll.deductions_delay +
            payroll.insurance + payroll.other_deductions
        )
        rows.append([
            payroll.employee.get_full_name() if payroll.employee else 'غير محدد',
            payroll.employee.department.name if payroll.employee and payroll.employee.department else 'غير محدد',
            f'{payroll.basic_salary:.2f}',
            f'{payroll.allowances:.2f}',
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
