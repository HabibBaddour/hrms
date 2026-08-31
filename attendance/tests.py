from datetime import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import AttendanceLog


class AttendanceLogTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='employee1', password='strongpass123')

    def test_attendance_log_model_exists_and_can_be_created(self):
        log = AttendanceLog.objects.create(
            employee=self.user,
            date='2026-08-31',
            check_in='2026-08-31 08:15:00',
            check_out='2026-08-31 17:30:00',
            status='حاضر',
        )
        self.assertEqual(log.employee, self.user)
        self.assertEqual(log.status, 'حاضر')

    def test_attendance_list_view_returns_ok_for_logged_in_user(self):
        self.client.login(username='employee1', password='strongpass123')
        response = self.client.get(reverse('attendance:attendance_list'))
        self.assertEqual(response.status_code, 200)

    def test_attendance_list_view_context_has_totals_for_logged_in_user(self):
        AttendanceLog.objects.create(
            employee=self.user,
            date='2026-08-31',
            check_in=datetime(2026, 8, 31, 8, 0, 0),
            check_out=datetime(2026, 8, 31, 17, 30, 0),
            status='حاضر',
        )
        AttendanceLog.objects.create(
            employee=self.user,
            date='2026-09-01',
            check_in=datetime(2026, 9, 1, 9, 0, 0),
            check_out=datetime(2026, 9, 1, 12, 30, 0),
            status='تأخير',
        )

        self.client.login(username='employee1', password='strongpass123')
        response = self.client.get(reverse('attendance:attendance_list'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['days_present'], 1)
        self.assertEqual(response.context['total_working_hours'], 9.5)
        self.assertIn('attendance_logs', response.context)
