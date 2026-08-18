from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from departments.models import Department, Position
from employees.models import Employee
from leaves.models import LeaveRequest


class LeaveWorkflowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='hradmin', password='secret123')
        self.user.is_staff = True
        self.user.save()
        self.employee = Employee.objects.create(user=self.user, first_name='Ali', last_name='Hassan')
        self.leave = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type='ANNUAL',
            start_date='2026-08-10',
            end_date='2026-08-12',
            reason='Family visit',
            status='PENDING',
        )

    def test_approve_leave_view_updates_status(self):
        self.client.login(username='hradmin', password='secret123')
        url = reverse('leaves:approve_leave', args=[self.leave.pk])
        response = self.client.post(url, {'decision': 'APPROVED', 'manager_notes': 'Approved by HR'})
        self.assertEqual(response.status_code, 302)
        self.leave.refresh_from_db()
        self.assertEqual(self.leave.status, 'APPROVED')
        self.assertEqual(self.leave.manager_notes, 'Approved by HR')

    def test_leave_list_filters_by_department_role_and_search(self):
        self.client.login(username='hradmin', password='secret123')

        finance = Department.objects.create(name='Finance', code='FIN')
        engineering = Department.objects.create(name='Engineering', code='ENG')

        manager_position = Position.objects.create(title='Senior Manager', department=finance, role='Manager')
        other_position = Position.objects.create(title='Engineer', department=engineering, role='Employee')

        manager_employee = Employee.objects.create(
            first_name='Sara',
            last_name='Nader',
            department=finance,
            position=manager_position,
        )
        Employee.objects.create(
            first_name='Omar',
            last_name='Saleh',
            department=engineering,
            position=other_position,
        )

        LeaveRequest.objects.create(
            employee=manager_employee,
            leave_type='ANNUAL',
            start_date='2026-09-01',
            end_date='2026-09-02',
            reason='Annual leave',
            status='PENDING',
        )
        LeaveRequest.objects.create(
            employee=manager_employee,
            leave_type='SICK',
            start_date='2026-09-03',
            end_date='2026-09-03',
            reason='Sick leave',
            status='APPROVED',
        )

        response = self.client.get(reverse('leaves:leave_list'), {
            'department': str(finance.id),
            'role': 'Manager',
            'q': 'Sara',
            'leave_type': 'ANNUAL',
            'status': 'PENDING',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['leaves']), 1)
        self.assertEqual(response.context['leaves'][0].employee, manager_employee)
