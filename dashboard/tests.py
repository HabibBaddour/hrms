from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from departments.models import Department, Position
from employees.models import Employee


class MessageRecipientFilterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='admin', password='testpass123')
        self.client.force_login(self.user)

        self.department = Department.objects.create(name='Engineering', code='ENG', description='Tech')
        self.manager_role = Position.objects.create(
            title='Team Lead',
            department=self.department,
            role='Manager',
        )
        self.employee_role = Position.objects.create(
            title='Developer',
            department=self.department,
            role='Employee',
        )

        self.manager_user = User.objects.create_user(username='manager', password='testpass123', first_name='Ali', last_name='Hassan')
        self.employee_user = User.objects.create_user(username='developer', password='testpass123', first_name='Sara', last_name='Khaled')

        Employee.objects.create(user=self.manager_user, department=self.department, position=self.manager_role)
        Employee.objects.create(user=self.employee_user, department=self.department, position=self.employee_role)

    def test_get_department_users_filters_by_role(self):
        response = self.client.get(reverse('get_department_users'), {
            'department_ids': str(self.department.id),
            'role': 'Manager',
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()['users']
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['full_name'], 'Ali Hassan')
        self.assertEqual(data[0]['role'], 'Manager')
