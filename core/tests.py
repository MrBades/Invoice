from django.test import TestCase
from django.urls import reverse

class DashboardTest(TestCase):
    def test_dashboard_load(self):
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 200)
