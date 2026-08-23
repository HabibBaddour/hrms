from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from departments.models import Department, Position
from employees.models import Employee
from payroll.models import Payroll


class PayrollDashboardTotalTest(TestCase):
    def test_dashboard_total_includes_all_payroll_records(self):
        user = get_user_model().objects.create_user(username='admin', password='admin123')
        department = Department.objects.create(name='IT', code='IT')

        for index in range(11):
            employee_user = get_user_model().objects.create_user(
                username=f'employee{index}',
                password='pass123',
            )
            employee = Employee.objects.create(
                user=employee_user,
                department=department,
                position=Position.objects.create(
                    title=f'Engineer {index}',
                    department=department,
                    base_salary=Decimal('2000.00'),
                ),
                first_name=f'Emp{index}',
                last_name='Test',
            )
            Payroll.objects.create(
                employee=employee,
                month=1,
                year=2026 + index,
                basic_salary=Decimal('2000.00'),
                allowances=Decimal('200.00'),
                deductions_absence=Decimal('0.00'),
                deductions_delay=Decimal('0.00'),
                insurance=Decimal('0.00'),
                other_deductions=Decimal('0.00'),
            )

        oldest = Payroll.objects.order_by('created_at').first()
        oldest.net_salary = Decimal('5000.00')
        oldest.save(update_fields=['net_salary'])

        self.client.force_login(user)
        response = self.client.get(reverse('payroll_dashboard'))

        expected_total = sum(
            (payroll.net_salary for payroll in Payroll.objects.all()),
            Decimal('0')
        )

        self.assertEqual(response.context['total_net_salary'], expected_total)
        self.assertEqual(response.context['processed_count'], Payroll.objects.count())


class PayrollDashboardFallbackTest(TestCase):
    def test_department_filter_uses_active_employee_salaries_without_payrolls(self):
        user = get_user_model().objects.create_user(username='admin', password='admin123')
        department = Department.objects.create(name='Information Technology', code='IT')
        position = Position.objects.create(
            title='Engineer',
            department=department,
            base_salary=Decimal('2000.00'),
        )
        active_employee = Employee.objects.create(
            user=get_user_model().objects.create_user(
                username='active_employee',
                password='pass123',
                is_active=True,
            ),
            department=department,
            position=position,
            salary=Decimal('2500.00'),
        )
        Employee.objects.create(
            user=get_user_model().objects.create_user(
                username='inactive_employee',
                password='pass123',
                is_active=False,
            ),
            department=department,
            position=position,
            salary=Decimal('3500.00'),
        )

        self.client.force_login(user)
        response = self.client.get(
            reverse('payroll_dashboard'),
            {'department': department.pk, 'month': '3', 'year': '2026'},
        )

        self.assertEqual(response.context['employee_count'], 1)
        self.assertEqual(response.context['filtered_count'], 1)
        self.assertEqual(response.context['total_base'], Decimal('2500.00'))
        self.assertEqual(response.context['total_net_salary'], Decimal('2500.00'))
        self.assertContains(response, active_employee.get_full_name())
        self.assertContains(response, '2500.00')
        self.assertNotContains(response, 'inactive_employee')
