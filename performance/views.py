from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils.dateparse import parse_date
from types import SimpleNamespace

from departments.models import Department
from employees.models import Employee
from performance.models import PerformanceEvaluation
from .forms import EvaluationDispatchForm, PerformanceEvaluationForm


def _get_dynamic_overall_score(evaluation):
    """Return the average of rated dynamic questions, ignoring legacy fields."""
    ratings = [
        question.get('rating')
        for question in (evaluation.question_schema or [])
        if isinstance(question.get('rating'), (int, float))
        and not isinstance(question.get('rating'), bool)
    ]
    return round(sum(ratings) / len(ratings), 2) if ratings else None


def _format_score(score):
    """Format a score without trailing zeroes while keeping whole scores readable."""
    if score is None:
        return ''
    if float(score).is_integer():
        return f'{score:.1f}'
    return f'{score:.2f}'.rstrip('0').rstrip('.')


def _campaign_key(evaluation):
    """Identify one dispatch campaign from the fields shared by its records."""
    return (
        evaluation.title,
        evaluation.employee.department_id,
        evaluation.evaluator_id,
        evaluation.evaluation_date,
    )


def _build_campaigns(evaluations):
    """Group individual evaluation records into display-ready campaign summaries."""
    grouped = {}
    for evaluation in evaluations:
        grouped.setdefault(_campaign_key(evaluation), []).append(evaluation)

    campaigns = []
    for records in grouped.values():
        first_record = records[0]
        completed_count = sum(
            record.status == 'COMPLETED'
            for record in records
        )
        campaigns.append(SimpleNamespace(
            campaign_id=min(record.pk for record in records),
            title=first_record.title,
            department_name=(
                first_record.employee.department.name
                if first_record.employee.department else 'غير محدد'
            ),
            evaluator_name=(
                first_record.evaluator.get_full_name()
                or first_record.evaluator.user.username
                if first_record.evaluator else 'غير محدد'
            ),
            created_date=first_record.evaluation_date,
            completed_count=completed_count,
            total_count=len(records),
            completion_display=f'{completed_count}/{len(records)}',
        ))
    return campaigns


def _get_performance_navigation(request):
    """Build role-aware links for performance pages and dashboard navigation."""
    employee_profile = getattr(request.user, 'employee_profile', None)
    role = getattr(getattr(employee_profile, 'position', None), 'role', '')
    normalized_role = role.strip().lower() if role else ''
    is_hr = (
        request.user.is_superuser
        or request.user.is_staff
        or normalized_role in {'hr', 'hr admin'}
        or request.user.groups.filter(name__iexact='HR').exists()
    )
    is_manager = normalized_role == 'manager'

    if is_hr:
        return {
            'back_url': reverse('performance_dashboard'),
            'dashboard_url': reverse('admin_dashboard'),
        }
    if is_manager:
        return {
            'back_url': reverse('team_performance'),
            'dashboard_url': reverse('manager_dashboard'),
        }
    return {
        'back_url': reverse('performance_dashboard'),
        'dashboard_url': reverse('dashboard'),
    }


@login_required(login_url='login')
def performance_dashboard(request):
    evaluations = PerformanceEvaluation.objects.select_related(
        'employee__user', 'employee__department', 'employee__position', 'evaluator__user'
    ).order_by('-evaluation_date', '-pk')
    selected_title = request.GET.get('title', '').strip()
    selected_department = request.GET.get('department', '').strip()
    selected_created_at = request.GET.get('created_at', '').strip()

    if selected_title:
        evaluations = evaluations.filter(title__icontains=selected_title)
    if selected_department.isdigit():
        evaluations = evaluations.filter(employee__department_id=selected_department)
    if selected_created_at:
        created_date = parse_date(selected_created_at)
        if created_date:
            evaluations = evaluations.filter(evaluation_date=created_date)

    campaign_records = list(evaluations)
    context = {
        'campaigns': _build_campaigns(campaign_records),
        'departments': Department.objects.all().order_by('name'),
        'selected_title': selected_title,
        'selected_department': selected_department,
        'selected_created_at': selected_created_at,
    }
    return render(request, 'performance/performance_dashboard.html', context)


@login_required(login_url='login')
def campaign_detail(request, campaign_id):
    anchor = get_object_or_404(
        PerformanceEvaluation.objects.select_related(
            'employee__department', 'employee__position', 'evaluator__user'
        ),
        pk=campaign_id,
    )
    campaign_evaluations = list(
        PerformanceEvaluation.objects.select_related(
            'employee__user', 'employee__position', 'employee__department',
        ).filter(
            title=anchor.title,
            employee__department_id=anchor.employee.department_id,
            evaluator_id=anchor.evaluator_id,
            evaluation_date=anchor.evaluation_date,
        ).order_by('employee__user__first_name', 'employee__user__last_name', 'pk')
    )

    for evaluation in campaign_evaluations:
        dynamic_score = _get_dynamic_overall_score(evaluation)
        if evaluation.status == 'COMPLETED':
            final_score = dynamic_score if dynamic_score is not None else evaluation.overall_score
            evaluation.final_score = final_score
            evaluation.score_display = _format_score(final_score)
            evaluation.status_display = 'مكتمل'
        else:
            evaluation.final_score = None
            evaluation.score_display = 'لم يقيّم بعد'
            evaluation.status_display = 'لم يقيّم بعد'

    campaign = _build_campaigns(campaign_evaluations)[0]
    return render(request, 'performance/campaign_detail.html', {
        'campaign': campaign,
        'campaign_evaluations': campaign_evaluations,
        'completed_count': sum(item.status == 'COMPLETED' for item in campaign_evaluations),
        'total_count': len(campaign_evaluations),
        **_get_performance_navigation(request),
    })


@login_required(login_url='login')
def team_performance(request):
    employee_profile = getattr(request.user, 'employee_profile', None)
    pending_evaluations = get_manager_pending_evaluations(employee_profile)
    team_employees = Employee.objects.none()
    if employee_profile and employee_profile.department_id:
        team_employees = Employee.objects.select_related(
            'user', 'position'
        ).filter(
            department_id=employee_profile.department_id,
            user__is_active=True,
        ).order_by('user__first_name', 'user__last_name', 'pk')

    return render(request, 'performance/team_performance.html', {
        'pending_evaluations': pending_evaluations,
        'team_employees': team_employees,
        'team_count': team_employees.count(),
        'pending_count': pending_evaluations.count(),
        'employee_profile': employee_profile,
        **_get_performance_navigation(request),
    })


def _get_department_evaluator(department):
    """Resolve the active department head, then an active department manager."""
    department_employees = Employee.objects.select_related(
        'user', 'position', 'department'
    ).filter(
        department=department,
        user__is_active=True,
    )
    return (
        department_employees.filter(position__is_head=True).order_by('pk').first()
        or department_employees.filter(position__role='Manager').order_by('pk').first()
    )


def _render_dispatch_form(request, form):
    return render(request, 'performance/add_evaluation.html', {
        'form': form,
        'departments': form.fields['department_id'].queryset,
        'question_values': getattr(form, 'question_values', ['']),
    })


def get_manager_pending_evaluations(employee_profile):
    """Return only drafts assigned to this manager and their department."""
    if not employee_profile or not employee_profile.department_id:
        return PerformanceEvaluation.objects.none()
    return PerformanceEvaluation.objects.select_related(
        'employee__user', 'employee__department', 'employee__position',
    ).filter(
        evaluator=employee_profile,
        employee__department_id=employee_profile.department_id,
        employee__position__role='Employee',
        status='DRAFT',
    ).order_by('-evaluation_date', '-pk')


@login_required(login_url='login')
def add_evaluation(request):
    form = EvaluationDispatchForm(request.POST or None)
    if not form.is_valid():
        return _render_dispatch_form(request, form)

    department = form.cleaned_data['department_id']
    evaluator = _get_department_evaluator(department)
    if evaluator is None:
        form.add_error(
            None,
            'لا يوجد مدير نشط أو رئيس قسم معيّن للقسم المحدد.',
        )
        return _render_dispatch_form(request, form)

    questions = [
        {'text': text, 'max_rating': 5, 'rating': None}
        for text in form.cleaned_questions
    ]
    employees = Employee.objects.select_related(
        'user', 'department', 'position'
    ).filter(
        department=department,
        user__is_active=True,
    ).exclude(
        pk=evaluator.pk,
    ).exclude(
        position__role='Manager',
    ).order_by('user__first_name', 'user__last_name', 'pk')

    with transaction.atomic():
        for employee in employees:
            PerformanceEvaluation.objects.create(
                title=form.cleaned_data['title'],
                employee=employee,
                evaluator=evaluator,
                period=form.cleaned_data['title'][:50],
                period_type='ANNUAL',
                status='DRAFT',
                work_quality=0,
                commitment=0,
                cooperation=0,
                overall_score=0,
                feedback='',
                question_schema=questions,
            )

    messages.success(request, 'تم إرسال التقييم إلى القسم المحدد.')
    return redirect('performance_dashboard')


@login_required(login_url='login')
def evaluation_detail(request, pk):
    evaluation = get_object_or_404(
        PerformanceEvaluation.objects.select_related(
            'employee__user', 'employee__department', 'evaluator__user'
        ),
        pk=pk,
    )
    employee_profile = getattr(request.user, 'employee_profile', None)
    can_fill = (
        evaluation.status == 'DRAFT'
        and employee_profile is not None
        and evaluation.evaluator_id == employee_profile.pk
        and evaluation.employee.department_id == employee_profile.department_id
    )
    if request.method == 'POST':
        if evaluation.status == 'DRAFT':
            if not can_fill:
                return HttpResponseForbidden('لا تملك صلاحية تعبئة هذا التقييم.')
            ratings = request.POST.getlist('rating')
            updated_questions = []
            for index, question in enumerate(evaluation.question_schema or []):
                try:
                    rating = int(ratings[index])
                except (IndexError, TypeError, ValueError):
                    rating = 0
                if rating < 1 or rating > question.get('max_rating', 5):
                    return _render_evaluation_detail(
                        request,
                        evaluation,
                        form_error='أدخل تقييماً بين 1 و5 لكل سؤال.',
                        can_fill=can_fill,
                    )
                updated_questions.append({
                    **question,
                    'rating': rating,
                })
            evaluation.question_schema = updated_questions
            evaluation.status = 'COMPLETED'
            evaluation.feedback = request.POST.get('feedback', '').strip()
            evaluation.save()
            messages.success(request, 'تم حفظ تقييم الموظف بنجاح.')
            return redirect('evaluation_detail', pk=evaluation.pk)

        return HttpResponseForbidden('طلب تحديث التقييم غير صالح.')

    return _render_evaluation_detail(request, evaluation, can_fill=can_fill)


def _render_evaluation_detail(request, evaluation, *, can_fill=False, form_error=''):
    history = PerformanceEvaluation.objects.filter(
        employee=evaluation.employee
    ).exclude(pk=evaluation.pk).order_by('-evaluation_date')
    return render(request, 'performance/evaluation_detail.html', {
        'evaluation': evaluation,
        'history': history,
        'can_fill': can_fill,
        'dynamic_overall_score': _get_dynamic_overall_score(evaluation),
        'form_error': form_error,
        **_get_performance_navigation(request),
    })
