from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden, QueryDict
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils.dateparse import parse_date
from types import SimpleNamespace

from departments.models import Department
from employees.models import Employee
from performance.models import PerformanceEvaluation, PerformanceQuestion, EvaluationDraft
from .forms import EvaluationDispatchForm, PerformanceEvaluationForm


def _parse_scale(raw_value, default=5):
    """Coerce a question scale value into a sane 1..10 integer."""
    try:
        scale = int(raw_value)
    except (TypeError, ValueError):
        scale = default
    return scale if 1 <= scale <= 10 else default


def _parse_tag(raw_value):
    """Normalize an essential/target skill tag keyword into its stored value."""
    normalized = (raw_value or '').strip().lower()
    if normalized in {'essential', 'أساسي', 'اساسي', 'essential skill'}:
        return 'essential'
    if normalized in {'target', 'مستهدف', 'target skill'}:
        return 'target'
    return ''


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


def _grade_label(score):
    """Translate a 1-5 score into a readable performance grade label."""
    if score is None:
        return '—'
    if score >= 4.5:
        return 'ممتاز'
    if score >= 3.5:
        return 'جيد جداً'
    if score >= 2.5:
        return 'جيد'
    if score >= 1.5:
        return 'مقبول'
    return 'ضعيف'


def _campaign_key(evaluation):
    """Identify one dispatch campaign from the fields shared by its records."""
    return (
        evaluation.title,
        evaluation.employee.department_id,
        evaluation.evaluator_id,
        evaluation.evaluation_date,
    )


def _get_evaluator_role(evaluator):
    """Return the human-readable role/title of the evaluator if available."""
    if evaluator is None:
        return 'غير محدد'
    position = getattr(evaluator, 'position', None)
    role = getattr(position, 'role', '')
    title = getattr(position, 'title', '')
    if title:
        return title
    if role:
        return role
    return 'مدير قسم'


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
        total_count = len(records)
        status = 'COMPLETED' if completed_count == total_count else 'IN_PROGRESS'
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
            evaluator_role=_get_evaluator_role(first_record.evaluator),
            created_date=first_record.evaluation_date,
            completed_count=completed_count,
            total_count=total_count,
            completion_display=f'{completed_count}/{total_count}',
            status=status,
            status_display='مكتملة' if status == 'COMPLETED' else 'قيد التنفيذ',
            completion_percent=round(completed_count / total_count * 100) if total_count else 0,
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
        'drafts': EvaluationDraft.objects.order_by('-updated_at'),
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
            evaluation.score_percent = round((final_score / 5) * 100)
            evaluation.grade_display = _grade_label(final_score)
            evaluation.status_display = 'مكتمل'
        else:
            evaluation.final_score = None
            evaluation.score_display = 'لم يقيّم بعد'
            evaluation.score_percent = None
            evaluation.grade_display = '—'
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


def _render_dispatch_form(request, form, draft=None):
    categories = getattr(form, 'categories', [])
    tab_builders = []
    for category in categories:
        values = getattr(form, 'category_values', {}).get(category.code, [''])
        scales = getattr(form, 'category_scales', {}).get(category.code, [5])
        nas = getattr(form, 'category_nas', {}).get(category.code, [False])
        tags = getattr(form, 'category_tags', {}).get(category.code, [''])
        tab_builders.append({
            'category': category,
            'rows': [
                (
                    value,
                    _parse_scale(scales[index]) if index < len(scales) else 5,
                    bool(nas[index]) if index < len(nas) else False,
                    tags[index] if index < len(tags) else '',
                )
                for index, value in enumerate(values)
            ],
        })
    active_type = (
        form.data.get('evaluation_type')
        if getattr(form, 'data', None) else ''
    ) or 'COMPETENCIES'
    return render(request, 'performance/add_evaluation.html', {
        'form': form,
        'departments': form.fields['departments'].queryset,
        'selected_department_ids': getattr(form, 'selected_department_ids', []),
        'question_values': getattr(form, 'question_values', ['']),
        'categories': categories,
        'tab_builders': tab_builders,
        'active_type': active_type,
        'draft': draft,
    })


def _build_draft_questions(raw_post, categories):
    """Build the question schema used by saved drafts from raw POST data."""
    questions = []
    for category in categories:
        texts = raw_post.getlist(f'questions_{category.code}')
        scales = raw_post.getlist(f'scale_{category.code}')
        nas = raw_post.getlist(f'na_{category.code}')
        tags = raw_post.getlist(f'tag_{category.code}')
        for index, text in enumerate(texts):
            text = text.strip()
            if not text:
                continue
            questions.append({
                'category': category.code,
                'text': text,
                'max_rating': _parse_scale(scales[index] if index < len(scales) else 5),
                'na': nas[index] == '1' if index < len(nas) else False,
                'tag': _parse_tag(tags[index] if index < len(tags) else ''),
            })
    return questions


def _save_evaluation_draft(request):
    """Persist an unfinished evaluation campaign so it can be continued later."""
    form = EvaluationDispatchForm(request.POST or None)
    title = request.POST.get('title', '').strip()
    if not title:
        form.add_error('title', 'أدخل عنواناً للتقييم قبل الحفظ كمسودة.')
        return _render_dispatch_form(request, form)

    questions = _build_draft_questions(request.POST, form.categories)
    department_ids = [value for value in request.POST.getlist('departments') if value.isdigit()]
    departments = Department.objects.filter(id__in=department_ids).order_by('name')

    draft_id = request.POST.get('draft_id', '')
    draft = EvaluationDraft.objects.filter(pk=draft_id).first() if draft_id.isdigit() else None
    if draft is None:
        draft = EvaluationDraft.objects.create(title=title, questions=questions)
    else:
        draft.title = title
        draft.questions = questions
        draft.save(update_fields=['title', 'questions'])
    draft.departments.set(departments)

    messages.success(request, 'تم حفظ التقييم كمسودة. يمكنك متابعة إعداده ونشره لاحقاً.')
    return redirect('performance_dashboard')


@login_required(login_url='login')
def draft_edit(request, pk):
    """Reopen a saved draft with all its questions, scales, and departments."""
    draft = get_object_or_404(EvaluationDraft, pk=pk)
    data = QueryDict(mutable=True)
    data['title'] = draft.title
    data['evaluation_type'] = 'COMPETENCIES'
    for department in draft.departments.all():
        data.appendlist('departments', str(department.pk))
    for question in draft.questions or []:
        data.appendlist(f'questions_{question.get("category")}', question.get('text', ''))
        data.appendlist(f'scale_{question.get("category")}', str(question.get('max_rating', 5)))
        data.appendlist(f'na_{question.get("category")}', '1' if question.get('na') else '0')
        data.appendlist(f'tag_{question.get("category")}', question.get('tag', '') or '')
    form = EvaluationDispatchForm(data)
    return _render_dispatch_form(request, form, draft=draft)


@login_required(login_url='login')
def draft_delete(request, pk):
    """Delete a saved evaluation draft permanently."""
    draft = get_object_or_404(EvaluationDraft, pk=pk)
    if request.method == 'POST':
        draft.delete()
        messages.success(request, 'تم حذف المسودة بنجاح.')
        return redirect('performance_dashboard')
    return redirect('performance_dashboard')


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
    if request.method == 'POST' and request.POST.get('action') == 'draft':
        return _save_evaluation_draft(request)

    form = EvaluationDispatchForm(request.POST or None)
    if not form.is_valid():
        return _render_dispatch_form(request, form)

    departments = form.cleaned_data['departments']
    if not departments:
        form.add_error('departments', 'اختر قسماً واحداً على الأقل.')
        return _render_dispatch_form(request, form)

    category_map = {category.code: category for category in form.categories}
    question_rows = []
    question_schema = []
    post_data = form.data
    for category in form.categories:
        raw_texts = post_data.getlist(f'questions_{category.code}')
        scales = post_data.getlist(f'scale_{category.code}')
        nas = post_data.getlist(f'na_{category.code}')
        tags = post_data.getlist(f'tag_{category.code}')
        for index, raw_text in enumerate(raw_texts):
            text = raw_text.strip()
            if not text:
                continue
            is_na = nas[index] == '1' if index < len(nas) else False
            tag = _parse_tag(tags[index] if index < len(tags) else '')
            max_rating = _parse_scale(scales[index] if index < len(scales) else 5)
            question_schema.append({
                'category': category.code,
                'text': text,
                'max_rating': max_rating,
                'rating': None,
                'na': is_na,
                'tag': tag,
            })
            question_rows.append((category, text, max_rating, is_na, tag))

    main_type = next(
        (
            category.code
            for category in form.categories
            if form.cleaned_questions_by_category.get(category.code)
        ),
        'COMPETENCIES',
    )

    evaluators = {}
    department_labels = []
    for department in departments:
        evaluator = _get_department_evaluator(department)
        if evaluator is None:
            form.add_error(
                None,
                f'لا يوجد مدير نشط أو رئيس قسم معيّن لقسم "{department.name}".',
            )
            return _render_dispatch_form(request, form)
        evaluators[department.pk] = evaluator
        department_labels.append(department.name)

    created_count = 0
    with transaction.atomic():
        for department in departments:
            evaluator = evaluators[department.pk]
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

            for employee in employees:
                evaluation = PerformanceEvaluation.objects.create(
                    title=form.cleaned_data['title'],
                    evaluation_type=main_type,
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
                    question_schema=question_schema,
                )
                evaluation.departments.add(department)
                for order, (category, text, max_rating, is_na, tag) in enumerate(question_rows, start=1):
                    PerformanceQuestion.objects.create(
                        evaluation=evaluation,
                        category=category,
                        text=text,
                        max_score=max_rating,
                        order=order,
                        is_na=is_na,
                        tag=tag,
                    )
                created_count += 1

    if created_count == 0:
        messages.warning(
            request,
            'لم يُنشأ أي تقييم؛ لا يوجد موظفون نشطون في الأقسام المحددة.',
        )
    elif len(departments) == 1:
        messages.success(
            request,
            f'تم إرسال التقييم إلى القسم "{department_labels[0]}" بنجاح.',
        )
    else:
        messages.success(
            request,
            f'تم إرسال التقييم إلى {len(departments)} أقسام بنجاح.',
        )
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
            rating_index = 0
            for question in evaluation.question_schema or []:
                if question.get('na'):
                    updated_questions.append({**question, 'rating': None})
                    continue
                try:
                    rating = int(ratings[rating_index])
                except (IndexError, TypeError, ValueError):
                    rating = 0
                rating_index += 1
                if rating < 1 or rating > question.get('max_rating', 5):
                    return _render_evaluation_detail(
                        request,
                        evaluation,
                        form_error=f'أدخل تقييماً بين 1 و{question.get("max_rating", 5)} لكل سؤال.',
                        can_fill=can_fill,
                    )
                updated_questions.append({**question, 'rating': rating})
            evaluation.question_schema = updated_questions
            question_records = list(evaluation.questions.order_by('order', 'pk'))
            for index, question_record in enumerate(question_records):
                rating = (
                    updated_questions[index].get('rating')
                    if index < len(updated_questions) else None
                )
                question_record.rating = rating
                question_record.save(update_fields=['rating'])
            evaluation.status = 'COMPLETED'
            evaluation.feedback = request.POST.get('feedback', '').strip()
            evaluation.save()
            messages.success(request, 'تم حفظ تقييم الموظف بنجاح.')
            return redirect('evaluation_detail', pk=evaluation.pk)

        return HttpResponseForbidden('طلب تحديث التقييم غير صالح.')

    return _render_evaluation_detail(request, evaluation, can_fill=can_fill)


def _question_items(evaluation):
    """Normalize an evaluation's questions for display (schema dicts or records)."""
    items = []
    if evaluation.question_schema:
        for question in evaluation.question_schema:
            max_rating = question.get('max_rating') or 5
            items.append({
                'text': question.get('text', ''),
                'max_rating': max_rating,
                'rating': question.get('rating'),
                'na': bool(question.get('na')),
                'tag': question.get('tag', ''),
                'score_range': range(1, max_rating + 1),
            })
    else:
        for record in evaluation.questions.select_related('category').order_by('order', 'pk'):
            max_rating = record.max_score or 5
            items.append({
                'text': record.text,
                'max_rating': max_rating,
                'rating': record.rating,
                'na': record.is_na,
                'tag': record.tag,
                'score_range': range(1, max_rating + 1),
            })
    return items


def _render_evaluation_detail(request, evaluation, *, can_fill=False, form_error=''):
    history = PerformanceEvaluation.objects.filter(
        employee=evaluation.employee
    ).exclude(pk=evaluation.pk).order_by('-evaluation_date')
    return render(request, 'performance/evaluation_detail.html', {
        'evaluation': evaluation,
        'history': history,
        'can_fill': can_fill,
        'dynamic_overall_score': _get_dynamic_overall_score(evaluation),
        'display_questions': _question_items(evaluation),
        'form_error': form_error,
        **_get_performance_navigation(request),
    })
