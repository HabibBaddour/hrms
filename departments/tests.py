from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse

from .models import Department, Position


class PositionDetailTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='hr', password='password')
		self.department = Department.objects.create(name='Operations', code='OPS')
		self.employee_position = Position.objects.create(
			title='Analyst', department=self.department, role='Employee',
			salary_min=1000, salary_max=2000,
		)
		self.manager_position = Position.objects.create(
			title='Team Lead', department=self.department, role='Manager',
			salary_min=2000, salary_max=4000,
		)
		self.head_position = Position.objects.create(
			title='Department Head', department=self.department, is_head=True,
			salary_min=3000, salary_max=5000,
		)

	def test_department_positions_put_managers_and_heads_first(self):
		self.client.login(username='hr', password='password')

		response = self.client.get(reverse('departments:department_detail', args=[self.department.id]))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(
			list(response.context['positions']),
			[self.manager_position, self.head_position, self.employee_position],
		)

	def test_position_detail_updates_salary_range(self):
		self.client.login(username='hr', password='password')

		response = self.client.post(
			reverse('departments:position_detail', args=[self.employee_position.id]),
			{
				'title': 'Senior Analyst', 'role': 'Employee', 'group': '',
				'salary_min': '1800', 'salary_max': '3200', 'base_salary': '2400',
			},
		)

		self.assertRedirects(response, reverse('departments:position_detail', args=[self.employee_position.id]))
		self.employee_position.refresh_from_db()
		self.assertEqual(self.employee_position.title, 'Senior Analyst')
		self.assertEqual(self.employee_position.salary_min, 1800)
		self.assertEqual(self.employee_position.salary_max, 3200)

	def test_position_detail_rejects_reversed_salary_range(self):
		self.client.login(username='hr', password='password')

		response = self.client.post(
			reverse('departments:position_detail', args=[self.employee_position.id]),
			{
				'title': 'Analyst', 'role': 'Employee', 'group': '',
				'salary_min': '3000', 'salary_max': '2000', 'base_salary': '2500',
			},
		)

		self.assertEqual(response.status_code, 200)
		self.employee_position.refresh_from_db()
		self.assertEqual(self.employee_position.salary_min, 1000)
		self.assertEqual(self.employee_position.salary_max, 2000)
