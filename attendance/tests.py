from calendar import monthrange
from datetime import date, datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from departments.models import Department
from employees.models import Employee

from .models import AttendanceLog
from .views import _team_month_aggregates


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

    def test_attendance_list_shows_full_month_rows_for_logged_in_user(self):
        today = timezone.localdate()
        first = today.replace(day=1)
        AttendanceLog.objects.create(
            employee=self.user,
            date=first,
            check_in=datetime(first.year, first.month, first.day, 8, 0, 0),
            check_out=datetime(first.year, first.month, first.day, 17, 30, 0),
            status='حاضر',
        )

        self.client.login(username='employee1', password='strongpass123')
        response = self.client.get(reverse('attendance:attendance_list'))

        self.assertEqual(response.status_code, 200)
        rows = response.context['attendance_rows']
        self.assertEqual(len(rows), monthrange(today.year, today.month)[1])
        self.assertTrue(any(row['is_today'] for row in rows))
        self.assertTrue(any(row['status'] == AttendanceLog.STATUS_PRESENT for row in rows))
        self.assertEqual(response.context['days_present'], 1)
        self.assertEqual(response.context['total_working_hours_text'], '9 ساعات و 30 دقيقة')
        self.assertIn('attendance_logs', response.context)

    def test_attendance_list_filters_rows_by_selected_month_and_year(self):
        AttendanceLog.objects.create(
            employee=self.user,
            date=date(2026, 8, 12),
            status=AttendanceLog.STATUS_PRESENT,
        )
        AttendanceLog.objects.create(
            employee=self.user,
            date=date(2026, 9, 1),
            status=AttendanceLog.STATUS_PRESENT,
        )

        self.client.login(username='employee1', password='strongpass123')
        response = self.client.get(
            reverse('attendance:attendance_list'),
            {'year': '2026', 'month': '8'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_year'], 2026)
        self.assertEqual(response.context['selected_month'], 8)
        self.assertEqual(len(response.context['attendance_rows']), 31)
        self.assertEqual(response.context['attendance_logs'].count(), 1)
        self.assertEqual(response.context['attendance_logs'].first().date, date(2026, 8, 12))

    def test_team_month_aggregates_include_daily_attendance_percentage_and_absent_members(self):
        department = Department.objects.create(name='Engineering', code='ENG')
        employee_two = User.objects.create_user(username='employee2', password='strongpass123')
        Employee.objects.create(user=self.user, department=department, first_name='Employee', last_name='One')
        Employee.objects.create(user=employee_two, department=department, first_name='Employee', last_name='Two')

        AttendanceLog.objects.create(
            employee=self.user,
            date=date(2026, 8, 1),
            status=AttendanceLog.STATUS_PRESENT,
        )
        AttendanceLog.objects.create(
            employee=employee_two,
            date=date(2026, 8, 1),
            status=AttendanceLog.STATUS_ABSENT,
        )

        _, daily = _team_month_aggregates(
            self.user,
            date(2026, 8, 1),
            date(2026, 9, 1),
        )

        day_data = next(item for item in daily if item['date'] == '2026-08-01')
        self.assertEqual(day_data['present'], 1)
        self.assertEqual(day_data['absent'], 1)
        self.assertEqual(day_data['attendance_percentage'], 50.0)
        self.assertEqual(day_data['absent_employees'], ['Employee Two'])