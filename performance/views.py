from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.db.models import Avg

from employees.models import Employee
from performance.models import PerformanceEvaluation
from .forms import PerformanceEvaluationForm


@login_required(login_url='login')
def performance_dashboard(request):
    evaluations = PerformanceEvaluation.objects.select_related(
        'employee__user', 'employee__department', 'employee__position', 'evaluator__user'
    ).order_by('-evaluation_date')
    period_type = request.GET.get('period_type')
    employee_id = request.GET.get('employee')
    if period_type:
        evaluations = evaluations.filter(period_type=period_type)
    if employee_id:
        evaluations = evaluations.filter(employee_id=employee_id)

    total_evaluations = evaluations.count()
    average_score = evaluations.aggregate(value=Avg('overall_score'))['value'] or 0
    top_score = evaluations.order_by('-overall_score').values_list('overall_score', flat=True).first() or 0
    latest_period = 'غير محدد'

    if total_evaluations:
        latest_period = evaluations.first().period

    context = {
        'evaluations': evaluations[:50],
        'total_evaluations': total_evaluations,
        'average_score': average_score,
        'top_score': top_score,
        'latest_period': latest_period,
        'employees': Employee.objects.select_related('user').order_by('user__first_name'),
        'selected_period_type': period_type or '',
        'selected_employee': employee_id or '',
    }
    return render(request, 'performance/performance_dashboard.html', context)


@login_required(login_url='login')
def add_evaluation(request):
    form = PerformanceEvaluationForm(request.POST or None)
    if form.is_valid():
        evaluator = getattr(request.user, 'employee_profile', None)
        evaluation = form.save(commit=False)
        evaluation.evaluator = evaluator
        evaluation.save()
        messages.success(request, f'تم تسجيل تقييم الأداء للموظف {evaluation.employee.get_full_name()} بنجاح.')
        return redirect('performance_dashboard')

    return render(request, 'performance/add_evaluation.html', {'form': form})


@login_required(login_url='login')
def evaluation_detail(request, pk):
    evaluation = get_object_or_404(
        PerformanceEvaluation.objects.select_related('employee__user', 'evaluator__user'), pk=pk
    )
    if request.method == 'POST':
        evaluation.employee_feedback = request.POST.get('employee_feedback', '').strip()
        evaluation.save(update_fields=('employee_feedback', 'updated_at'))
        messages.success(request, 'تم حفظ ملاحظات الموظف.')
        return redirect('evaluation_detail', pk=evaluation.pk)
    history = PerformanceEvaluation.objects.filter(employee=evaluation.employee).exclude(pk=evaluation.pk).order_by('-evaluation_date')
    return render(request, 'performance/evaluation_detail.html', {'evaluation': evaluation, 'history': history})
