from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from departments.models import Department, Position
from .models import Employee, EmployeePhone


class ProfileUpdateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='profile_user',
            email='profile@example.com',
            password='TestPass123',
            first_name='Test',
            last_name='User',
        )
        self.department = Department.objects.create(name='Human Resource', code='HR', description='HR department')
        self.position = Position.objects.create(
            department=self.department,
            title='HR Officer',
            role='Employee',
            base_salary=2500,
        )
        self.employee = Employee.objects.create(
            user=self.user,
            department=self.department,
            position=self.position,
            first_name='Test',
            last_name='User',
            phone='0500000000',
        )

    def test_profile_allows_user_to_update_personal_details_and_multiple_phones(self):
        self.client.login(username='profile_user', password='TestPass123')

        response = self.client.post(
            reverse('employees:profile'),
            {
                'date_of_birth': '1998-06-15',
                'address': 'Riyadh, Saudi Arabia',
                'primary_phone': '0501111111',
                'extra_phone_1': '0502222222',
                'extra_phone_2': '0503333333',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.date_of_birth, date(1998, 6, 15))
        self.assertEqual(self.employee.address, 'Riyadh, Saudi Arabia')
        self.assertEqual(self.employee.phone, '0501111111')

        phones = list(self.employee.phone_numbers.values_list('number', flat=True))
        self.assertIn('0501111111', phones)
        self.assertIn('0502222222', phones)
        self.assertIn('0503333333', phones)
