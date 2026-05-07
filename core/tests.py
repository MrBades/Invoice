from django.test import TestCase, Client
from django.urls import reverse
from .models import Customer, Invoice

class BasicFlowTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.customer = Customer.objects.create(name="Test Customer", phone_number="12345")

    def test_dashboard_status_code(self):
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('total_sales_sum', response.context)

    def test_invoice_list_status_code(self):
        response = self.client.get(reverse('core:invoice_list'))
        self.assertEqual(response.status_code, 200)
