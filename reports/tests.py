from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class ReportsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='reportviewer', password='secret123')

    def test_reports_dashboard_accessible(self):
        self.client.login(username='reportviewer', password='secret123')
        response = self.client.get(reverse('reports:reports_dashboard'))
        self.assertEqual(response.status_code, 200)
