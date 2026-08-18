from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect

from employees.models import Employee
from performance.models import PerformanceEvaluation


@login_required(login_url='login')
def performance_dashboard(request):
    evaluations = PerformanceEvaluation.objects.select_related(
        'employee__user', 'employee__department', 'employee__position', 'evaluator__user'
    ).order_by('-evaluation_date')[:10]

    total_evaluations = evaluations.count()
    average_score = 0
    top_score = 0
    latest_period = 'غير محدد'

    if evaluations:
        average_score = round(sum(item.overall_score for item in evaluations) / total_evaluations, 2)
        top_score = max(item.overall_score for item in evaluations)
        latest_period = evaluations[0].period

    context = {
        'evaluations': evaluations,
        'total_evaluations': total_evaluations,
        'average_score': average_score,
        'top_score': top_score,
        'latest_period': latest_period,
    }
    return render(request, 'performance/performance_dashboard.html', context)


@login_required(login_url='login')
def add_evaluation(request):
    employees = Employee.objects.select_related('user', 'department', 'position').all()

    if request.method == 'POST':
        employee_id = request.POST.get('employee')
        employee = get_object_or_404(Employee, pk=employee_id)
        evaluator = getattr(request.user, 'employee_profile', None)
        work_quality = int(request.POST.get('work_quality', 0))
        commitment = int(request.POST.get('commitment', 0))
        cooperation = int(request.POST.get('cooperation', 0))
        feedback = request.POST.get('feedback', '').strip()
        period = request.POST.get('period', 'Q1 2026')

        evaluation = PerformanceEvaluation.objects.create(
            employee=employee,
            evaluator=evaluator,
            period=period,
            work_quality=work_quality,
            commitment=commitment,
            cooperation=cooperation,
            feedback=feedback,
        )
        messages.success(request, f'تم تسجيل تقييم الأداء للموظف {employee.get_full_name()} بنجاح.')
        return redirect('performance_dashboard')

    return render(request, 'performance/add_evaluation.html', {'employees': employees})
