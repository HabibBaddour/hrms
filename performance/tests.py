from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from departments.models import Department, Position
from employees.models import Employee
from performance.forms import EvaluationDispatchForm
from performance.models import PerformanceEvaluation, PerformanceQuestion, QuestionCategory


class EvaluationDispatchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categories = [
            QuestionCategory.objects.create(
                code=code, name=name, order=order,
            )
            for code, name, order in [
                ('COMPETENCIES', 'المهارات الوظيفية وجودة العمل', 1),
                ('BEHAVIORAL', 'السلوك والالتزام التنظيمي', 2),
                ('KPI_PRODUCTIVITY', 'الأهداف والإنتاجية', 3),
                ('INITIATIVE_GROWTH', 'التطوير والمبادرة', 4),
            ]
        ]

    def setUp(self):
        self.hr_user = get_user_model().objects.create_user(
            username='hr-admin',
            password='pass123',
        )
        self.department = Department.objects.create(
            name='Information Technology',
            code='IT',
        )
        self.head_position = Position.objects.create(
            title='Department Head',
            department=self.department,
            role='Manager',
            is_head=True,
        )
        self.employee_position = Position.objects.create(
            title='Engineer',
            department=self.department,
        )

    def _employee(self, username, *, position=None, is_active=True):
        return Employee.objects.create(
            user=get_user_model().objects.create_user(
                username=username,
                password='pass123',
                is_active=is_active,
            ),
            department=self.department,
            position=position or self.employee_position,
            first_name=username,
        )

    def _post_dispatch(self, questions=None):
        return self.client.post(reverse('add_evaluation'), {
            'title': 'تقييم الأداء النصف سنوي 2026',
            'evaluation_type': 'COMPETENCIES',
            'departments': [str(self.department.pk)],
            'questions_COMPETENCIES': list(questions or [
                'الالتزام بمواعيد تسليم المهام',
                'جودة التعاون مع الفريق',
            ]),
        })

    def test_dispatch_creates_one_draft_per_active_employee_with_head_evaluator(self):
        head = self._employee('department-head', position=self.head_position)
        employee_one = self._employee('employee-one')
        employee_two = self._employee('employee-two')
        self._employee('inactive-employee', is_active=False)
        self.client.force_login(self.hr_user)

        response = self._post_dispatch()

        self.assertRedirects(response, reverse('performance_dashboard'))
        evaluations = PerformanceEvaluation.objects.order_by('employee_id')
        self.assertEqual(evaluations.count(), 2)
        self.assertEqual(
            set(evaluations.values_list('employee_id', flat=True)),
            {employee_one.pk, employee_two.pk},
        )
        self.assertFalse(evaluations.filter(employee=head).exists())
        self.assertTrue(all(item.status == 'DRAFT' for item in evaluations))
        self.assertTrue(all(item.evaluator_id == head.pk for item in evaluations))
        self.assertEqual(
            evaluations.first().question_schema,
            [
                {'category': 'COMPETENCIES', 'text': 'الالتزام بمواعيد تسليم المهام', 'max_rating': 5, 'rating': None},
                {'category': 'COMPETENCIES', 'text': 'جودة التعاون مع الفريق', 'max_rating': 5, 'rating': None},
            ],
        )
        self.assertEqual(
            list(evaluations.first().questions.values_list('category__code', 'text')),
            [('COMPETENCIES', 'الالتزام بمواعيد تسليم المهام'), ('COMPETENCIES', 'جودة التعاون مع الفريق')],
        )
        self.assertTrue(all(item.overall_score == 0 for item in evaluations))
        self.assertTrue(all(item.evaluation_type == 'COMPETENCIES' for item in evaluations))

    def test_dispatch_saves_selected_evaluation_type(self):
        self._employee('department-head', position=self.head_position)
        self._employee('employee-one')
        self.client.force_login(self.hr_user)

        response = self.client.post(reverse('add_evaluation'), {
            'title': 'تقييم الأداء الربع ثاني',
            'evaluation_type': 'KPI_PRODUCTIVITY',
            'departments': [str(self.department.pk)],
            'questions_KPI_PRODUCTIVITY': ['قيس تحقيق الأهداف'],
        })

        self.assertRedirects(response, reverse('performance_dashboard'))
        evaluation = PerformanceEvaluation.objects.get()
        self.assertEqual(evaluation.evaluation_type, 'KPI_PRODUCTIVITY')
        self.assertEqual(evaluation.questions.count(), 1)
        self.assertEqual(evaluation.question_schema, [
            {'category': 'KPI_PRODUCTIVITY', 'text': 'قيس تحقيق الأهداف', 'max_rating': 5, 'rating': None},
        ])

    def test_dispatch_saves_questions_grouped_by_category_and_main_type_follows_tab_order(self):
        self._employee('department-head', position=self.head_position)
        self._employee('employee-one')
        self.client.force_login(self.hr_user)

        response = self.client.post(reverse('add_evaluation'), {
            'title': 'تقييم متعدد المحاور',
            'evaluation_type': 'INITIATIVE_GROWTH',
            'departments': [str(self.department.pk)],
            'questions_BEHAVIORAL': ['الالتزام'],
            'questions_INITIATIVE_GROWTH': ['المبادرة'],
        })

        self.assertRedirects(response, reverse('performance_dashboard'))
        evaluation = PerformanceEvaluation.objects.get()
        self.assertEqual(evaluation.evaluation_type, 'BEHAVIORAL')
        self.assertEqual(
            [(q['category'], q['text']) for q in evaluation.question_schema],
            [('BEHAVIORAL', 'الالتزام'), ('INITIATIVE_GROWTH', 'المبادرة')],
        )
        self.assertEqual(
            list(evaluation.questions.values_list('category__code', 'text', 'order')),
            [('BEHAVIORAL', 'الالتزام', 1), ('INITIATIVE_GROWTH', 'المبادرة', 2)],
        )

    def test_dispatch_handles_multiple_selected_departments(self):
        head = self._employee('department-head', position=self.head_position)
        employee_one = self._employee('employee-one')
        self._employee('employee-two')

        finance = Department.objects.create(name='Finance', code='FIN')
        finance_head_position = Position.objects.create(
            title='Finance Head',
            department=finance,
            role='Manager',
            is_head=True,
        )
        finance_head = Employee.objects.create(
            user=get_user_model().objects.create_user(
                username='finance-head', password='pass123',
            ),
            department=finance,
            position=finance_head_position,
            first_name='FinanceHead',
        )
        finance_employee_position = Position.objects.create(
            title='Accountant',
            department=finance,
            role='Employee',
        )
        finance_employee = Employee.objects.create(
            user=get_user_model().objects.create_user(
                username='finance-employee', password='pass123',
            ),
            department=finance,
            position=finance_employee_position,
            first_name='FinanceEmployee',
        )
        self.client.force_login(self.hr_user)

        response = self.client.post(reverse('add_evaluation'), {
            'title': 'تقييم موحّد',
            'evaluation_type': 'BEHAVIORAL',
            'departments': [str(self.department.pk), str(finance.pk)],
            'questions_BEHAVIORAL': ['الالتزام بالمواعيد'],
        })

        self.assertRedirects(response, reverse('performance_dashboard'))
        evaluations = PerformanceEvaluation.objects.order_by('employee_id')
        self.assertEqual(
            set(evaluations.values_list('employee_id', flat=True)),
            {employee_one.pk, finance_employee.pk},
        )
        self.assertEqual(
            set(evaluations.values_list('evaluator_id', flat=True)),
            {head.pk, finance_head.pk},
        )
        for evaluation in evaluations:
            self.assertEqual(
                set(evaluation.departments.values_list('name', flat=True)),
                {evaluation.employee.department.name},
            )

    def test_dispatch_records_selected_departments_on_each_record(self):
        head = self._employee('department-head', position=self.head_position)
        employee = self._employee('employee')
        self.client.force_login(self.hr_user)

        response = self._post_dispatch(['سؤال واحد'])

        self.assertRedirects(response, reverse('performance_dashboard'))
        evaluation = PerformanceEvaluation.objects.get(employee=employee)
        self.assertEqual(
            list(evaluation.departments.values_list('pk', flat=True)),
            [self.department.pk],
        )

    def test_hr_overview_groups_campaign_and_hides_zero_for_pending(self):
        manager = self._employee('department-manager', position=self.head_position)
        completed_employee = self._employee('completed-employee')
        pending_employee = self._employee('pending-employee')
        campaign_title = 'تقييم الربع الأول'
        completed = PerformanceEvaluation.objects.create(
            title=campaign_title,
            employee=completed_employee,
            evaluator=manager,
            period=campaign_title,
            status='COMPLETED',
            work_quality=4,
            commitment=4,
            cooperation=4,
            overall_score=4,
            feedback='',
            question_schema=[
                {'text': 'جودة العمل', 'max_rating': 5, 'rating': 4},
                {'text': 'التعاون', 'max_rating': 5, 'rating': 5},
            ],
        )
        pending = PerformanceEvaluation.objects.create(
            title=campaign_title,
            employee=pending_employee,
            evaluator=manager,
            period=campaign_title,
            status='DRAFT',
            work_quality=0,
            commitment=0,
            cooperation=0,
            overall_score=0,
            feedback='',
            question_schema=[{'text': 'جودة العمل', 'max_rating': 5, 'rating': None}],
        )
        self.client.force_login(self.hr_user)

        overview_response = self.client.get(reverse('performance_dashboard'))
        campaigns = overview_response.context['campaigns']
        self.assertEqual(len(campaigns), 1)
        self.assertEqual(campaigns[0].campaign_id, min(completed.pk, pending.pk))
        self.assertEqual(campaigns[0].completion_display, '1/2')
        self.assertContains(overview_response, 'اسم التقييم')
        self.assertContains(overview_response, 'نسبة الإنجاز')
        self.assertContains(
            overview_response,
            reverse('campaign_detail', args=[campaigns[0].campaign_id]),
        )
        self.assertNotContains(overview_response, 'الجودة')
        self.assertNotContains(overview_response, 'التعاون')

        detail_response = self.client.get(
            reverse('campaign_detail', args=[campaigns[0].campaign_id])
        )
        self.assertEqual(detail_response.context['completed_count'], 1)
        self.assertEqual(detail_response.context['total_count'], 2)
        self.assertContains(detail_response, '4.5/5')
        self.assertContains(detail_response, 'لم يقيّم بعد')
        self.assertNotContains(detail_response, '0.0/5')
        self.assertContains(detail_response, 'المناصب/المسمى الوظيفي')

    def test_hr_campaign_filters_preserve_values_and_filter_before_grouping(self):
        manager = self._employee('department-manager', position=self.head_position)
        employee = self._employee('employee')
        evaluation = PerformanceEvaluation.objects.create(
            title='حملة تقنية',
            employee=employee,
            evaluator=manager,
            period='حملة تقنية',
            status='DRAFT',
            work_quality=0,
            commitment=0,
            cooperation=0,
            overall_score=0,
            feedback='',
            question_schema=[{'text': 'سؤال', 'max_rating': 5, 'rating': None}],
        )
        other_department = Department.objects.create(name='Finance', code='FIN')
        other_manager_position = Position.objects.create(
            title='Finance Manager',
            department=other_department,
            role='Manager',
        )
        other_manager = Employee.objects.create(
            user=get_user_model().objects.create_user(username='finance-manager'),
            department=other_department,
            position=other_manager_position,
        )
        other_employee_position = Position.objects.create(
            title='Accountant',
            department=other_department,
            role='Employee',
        )
        other_employee = Employee.objects.create(
            user=get_user_model().objects.create_user(username='finance-employee'),
            department=other_department,
            position=other_employee_position,
        )
        PerformanceEvaluation.objects.create(
            title='حملة مالية',
            employee=other_employee,
            evaluator=other_manager,
            period='حملة مالية',
            status='DRAFT',
            work_quality=0,
            commitment=0,
            cooperation=0,
            overall_score=0,
            feedback='',
            question_schema=[{'text': 'سؤال', 'max_rating': 5, 'rating': None}],
        )
        self.client.force_login(self.hr_user)

        response = self.client.get(reverse('performance_list'), {
            'title': 'تقنية',
            'department': str(self.department.pk),
            'created_at': evaluation.evaluation_date.isoformat(),
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['campaigns']), 1)
        self.assertEqual(response.context['campaigns'][0].title, 'حملة تقنية')
        self.assertEqual(response.context['selected_title'], 'تقنية')
        self.assertEqual(response.context['selected_department'], str(self.department.pk))
        self.assertEqual(response.context['selected_created_at'], evaluation.evaluation_date.isoformat())
        self.assertContains(response, 'تقنية')
        self.assertNotContains(response, 'حملة مالية')

    def test_dispatch_falls_back_to_manager_when_no_department_head_exists(self):
        self.head_position.delete()
        manager_position = Position.objects.create(
            title='Manager',
            department=self.department,
            role='Manager',
        )
        manager = self._employee('manager', position=manager_position)
        self._employee('employee')
        self.client.force_login(self.hr_user)

        response = self._post_dispatch(['Question'])

        self.assertRedirects(response, reverse('performance_dashboard'))
        self.assertEqual(
            set(PerformanceEvaluation.objects.values_list('evaluator_id', flat=True)),
            {manager.pk},
        )

    def test_dispatch_requires_an_active_department_manager(self):
        self._employee('employee')
        self.client.force_login(self.hr_user)

        response = self._post_dispatch()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(PerformanceEvaluation.objects.count(), 0)
        self.assertContains(response, 'لا يوجد مدير نشط أو رئيس قسم')

    def test_dispatch_requires_a_title_and_question(self):
        self.client.force_login(self.hr_user)

        data = {
            'departments': [str(self.department.pk)],
            'evaluation_type': 'COMPETENCIES',
            'questions_COMPETENCIES': [''],
            'questions_BEHAVIORAL': [''],
            'questions_KPI_PRODUCTIVITY': [''],
            'questions_INITIATIVE_GROWTH': [''],
        }

        response = self.client.post(reverse('add_evaluation'), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(PerformanceEvaluation.objects.count(), 0)
        self.assertContains(response, 'عنوان التقييم')
        self.assertContains(response, 'أضف سؤال تقييم واحداً على الأقل.')

    def test_manager_dashboards_show_only_assigned_department_drafts(self):
        manager = self._employee('manager', position=self.head_position)
        employee = self._employee('employee')
        other_department = Department.objects.create(name='Finance', code='FIN')
        other_position = Position.objects.create(title='Accountant', department=other_department)
        other_employee = Employee.objects.create(
            user=get_user_model().objects.create_user(username='other-employee'),
            department=other_department,
            position=other_position,
        )
        evaluation = PerformanceEvaluation.objects.create(
            title='تقييم الفريق',
            employee=employee,
            evaluator=manager,
            period='تقييم الفريق',
            status='DRAFT',
            work_quality=0,
            commitment=0,
            cooperation=0,
            overall_score=0,
            feedback='',
            question_schema=[{'text': 'جودة العمل', 'max_rating': 5, 'rating': None}],
        )
        PerformanceEvaluation.objects.create(
            title='تقييم خارج الفريق',
            employee=other_employee,
            evaluator=manager,
            period='تقييم خارج الفريق',
            status='DRAFT',
            work_quality=0,
            commitment=0,
            cooperation=0,
            overall_score=0,
            feedback='',
            question_schema=[{'text': 'سؤال', 'max_rating': 5, 'rating': None}],
        )
        self.client.force_login(manager.user)

        dashboard_response = self.client.get(reverse('manager_dashboard'))
        team_response = self.client.get(reverse('team_performance'))

        self.assertEqual(list(dashboard_response.context['pending_evaluations']), [evaluation])
        self.assertEqual(list(team_response.context['pending_evaluations']), [evaluation])
        self.assertContains(dashboard_response, 'استمارات التقييم بانتظار التعبئة')
        self.assertContains(dashboard_response, 'تعبئة التقييم')
        self.assertContains(team_response, 'تعبئة التقييم')
        self.assertContains(team_response, 'عودة للوحة التحكم')
        self.assertContains(team_response, reverse('evaluation_detail', args=[evaluation.pk]))
        self.assertNotContains(team_response, 'تقييم خارج الفريق')

    def test_performance_navigation_is_role_aware(self):
        manager = self._employee('manager', position=self.head_position)
        employee = self._employee('employee')
        evaluation = PerformanceEvaluation.objects.create(
            title='تقييم الفريق',
            employee=employee,
            evaluator=manager,
            period='تقييم الفريق',
            status='DRAFT',
            work_quality=0,
            commitment=0,
            cooperation=0,
            overall_score=0,
            feedback='',
            question_schema=[{'text': 'جودة العمل', 'max_rating': 5, 'rating': None}],
        )

        self.hr_user.is_staff = True
        self.hr_user.save(update_fields=['is_staff'])
        self.client.force_login(self.hr_user)
        hr_response = self.client.get(reverse('evaluation_detail', args=[evaluation.pk]))

        self.assertEqual(hr_response.context['back_url'], reverse('performance_dashboard'))
        self.assertEqual(hr_response.context['dashboard_url'], reverse('admin_dashboard'))
        self.assertContains(hr_response, 'href="/performance/"')
        self.assertContains(hr_response, 'href="/dashboard/admin/"')

        self.client.force_login(manager.user)
        manager_response = self.client.get(reverse('evaluation_detail', args=[evaluation.pk]))

        self.assertEqual(manager_response.context['back_url'], reverse('team_performance'))
        self.assertEqual(manager_response.context['dashboard_url'], reverse('manager_dashboard'))
        self.assertContains(manager_response, 'href="/performance/team/"')
        self.assertContains(manager_response, 'href="/dashboard/manager/"')

    def test_evaluation_detail_has_no_employee_response_section(self):
        manager = self._employee('manager', position=self.head_position)
        employee = self._employee('employee')
        evaluation = PerformanceEvaluation.objects.create(
            title='تقييم الفريق',
            employee=employee,
            evaluator=manager,
            period='تقييم الفريق',
            status='COMPLETED',
            work_quality=4,
            commitment=4,
            cooperation=4,
            overall_score=4,
            feedback='ملاحظات المدير',
            question_schema=[{'text': 'سؤال الأداء', 'max_rating': 5, 'rating': 4}],
        )
        self.client.force_login(manager.user)

        response = self.client.get(reverse('evaluation_detail', args=[evaluation.pk]))

        self.assertNotContains(response, 'رد الموظف')
        self.assertNotContains(response, 'employee_feedback')
        self.assertNotContains(response, 'حفظ الملاحظات')
        self.assertContains(response, 'المتوسط العام للتقييم الديناميكي')
        self.assertContains(response, '4.0/5')

    def test_assigned_manager_can_fill_dynamic_ratings(self):
        manager = self._employee('manager', position=self.head_position)
        employee = self._employee('employee')
        evaluation = PerformanceEvaluation.objects.create(
            title='تقييم الفريق',
            employee=employee,
            evaluator=manager,
            period='تقييم الفريق',
            status='DRAFT',
            work_quality=0,
            commitment=0,
            cooperation=0,
            overall_score=0,
            feedback='',
            question_schema=[
                {'text': 'جودة العمل', 'max_rating': 5, 'rating': None},
                {'text': 'التعاون', 'max_rating': 5, 'rating': None},
            ],
        )
        self.client.force_login(manager.user)

        response = self.client.post(
            reverse('evaluation_detail', args=[evaluation.pk]),
            {'rating': ['4', '5'], 'feedback': 'أداء قوي'},
        )

        self.assertRedirects(response, reverse('evaluation_detail', args=[evaluation.pk]))
        evaluation.refresh_from_db()
        self.assertEqual(evaluation.status, 'COMPLETED')
        self.assertEqual(evaluation.overall_score, 4.5)
        self.assertEqual([item['rating'] for item in evaluation.question_schema], [4, 5])
        self.assertEqual(
            list(evaluation.questions.values_list('rating', flat=True)),
            [4, 5],
        )
