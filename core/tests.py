from django.test import TestCase
from django.urls import reverse
from .models import Invoice, Customer, Product, InvoiceItem
from decimal import Decimal

class DashboardTest(TestCase):
    def test_dashboard_load(self):
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 200)

class SmartInputTest(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name="Test Customer", phone_number="123456789")
        self.product = Product.objects.create(
            name="Bread",
            retail_price=Decimal("500.00"),
            wholesale_price=Decimal("450.00")
        )

    def test_smart_input_processing(self):
        # Text format: "[Product] [Amount] to [Customer]"
        smart_text = "Bread 1000 to Test Customer"
        response = self.client.post(reverse('core:smart_input_processor'), {'smart_text': smart_text})

        # Should redirect to detail or return HTMX fragment
        self.assertEqual(response.status_code, 302)

        # Check if invoice and invoice item were created
        invoice = Invoice.objects.last()
        self.assertEqual(invoice.customer.name, "Test Customer")
        self.assertEqual(invoice.subtotal, Decimal("1000.00"))

        item = InvoiceItem.objects.get(invoice=invoice)
        self.assertEqual(item.product.name, "Bread")
        self.assertEqual(item.total_price, Decimal("1000.00"))

    def test_dashboard_aggregations(self):
        # Create an invoice with some paid amount
        invoice = Invoice.objects.create(
            customer=self.customer,
            issue_date="2026-04-25",
            subtotal=Decimal("2000.00"),
            total_amount=Decimal("2150.00"),
            amount_paid=Decimal("500.00")
        )

        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2,150") # Total Invoiced
        self.assertContains(response, "1,650") # Total Debt (2150 - 500)
