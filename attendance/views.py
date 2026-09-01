import csv

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.html import escape

from .models import AttendanceLog

ARABIC_MONTHS = [
    'يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
    'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر',
]

STATUS_LABELS = {
    AttendanceLog.STATUS_PRESENT: 'حاضر',
    AttendanceLog.STATUS_LATE: 'متأخر',
    AttendanceLog.STATUS_ABSENT: 'غائب',
}


@login_required
def attendance_list_view(request):
    attendance_logs = AttendanceLog.objects.filter(employee=request.user)

    selected_month = request.GET.get('month', '')
    selected_year = request.GET.get('year', '')

    if selected_year.isdigit():
        attendance_logs = attendance_logs.filter(date__year=int(selected_year))
    if selected_month.isdigit():
        attendance_logs = attendance_logs.filter(date__month=int(selected_month))

    attendance_logs = attendance_logs.order_by('-date', '-check_in')

    export = request.GET.get('export')
    if export == 'excel':
        return _export_attendance_excel(attendance_logs)
    if export == 'pdf':
        return _export_attendance_pdf(attendance_logs)

    days_present = attendance_logs.filter(status=AttendanceLog.STATUS_PRESENT).count()

    total_working_hours = 0.0
    for log in attendance_logs:
        if log.check_in and log.check_out:
            delta = log.check_out - log.check_in
            if delta.total_seconds() > 0:
                total_working_hours += delta.total_seconds() / 3600

    this_year = timezone.now().year
    context = {
        'attendance_logs': attendance_logs,
        'days_present': days_present,
        'total_working_hours': float(total_working_hours),
        'selected_month': selected_month,
        'selected_year': selected_year,
        'month_options': [(number, ARABIC_MONTHS[number - 1]) for number in range(1, 13)],
        'year_options': [year_value for year_value in range(this_year, this_year - 6, -1)],
    }
    return render(request, 'attendance/attendance_list.html', context)


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
<h2>جدول الحضور والدوام</h2>
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