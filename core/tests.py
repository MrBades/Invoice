from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Customer, Invoice
from decimal import Decimal


class BasicFlowTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="password123")
        self.client.force_login(self.user)
        self.customer = Customer.objects.create(name="Test Customer", phone_number="12345", user=self.user)

    def test_dashboard_status_code(self):
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('total_sales_sum', response.context)

    def test_invoice_list_status_code(self):
        response = self.client.get(reverse('core:invoice_list'))
        self.assertEqual(response.status_code, 200)

    def test_quick_customer_create(self):
        # Create a new walk-in customer via HTMX
        response = self.client.post(reverse('core:quick_customer_create'), {
            'quick_name': 'Walkin Customer',
            'quick_phone': '08099998888'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Walkin Customer', response.content.decode())
        self.assertTrue(Customer.objects.filter(name='Walkin Customer', user=self.user).exists())

    def test_smart_input_processor(self):
        # 1. Standard pattern: "Rice 5k to Musa"
        response = self.client.post(reverse('core:smart_input_processor'), {
            'smart_text': 'Rice 5k to Musa'
        })
        self.assertIn(response.status_code, [200, 302])
        invoice = Invoice.objects.filter(customer__name='Musa', user=self.user).first()
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.subtotal, Decimal('5000.00'))
        self.assertEqual(invoice.total_amount, Decimal('5375.00')) # 5000 + 7.5% VAT

        # 2. No "to" preposition: "Rice 5k Musa"
        response = self.client.post(reverse('core:smart_input_processor'), {
            'smart_text': 'Rice 5k Musa'
        })
        self.assertIn(response.status_code, [200, 302])
        invoice = Invoice.objects.filter(customer__name='Musa', user=self.user).last()
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.subtotal, Decimal('5000.00'))

        # 3. Inverted order: "5k Rice Musa"
        response = self.client.post(reverse('core:smart_input_processor'), {
            'smart_text': '5k Rice Musa'
        })
        self.assertIn(response.status_code, [200, 302])
        invoice = Invoice.objects.filter(customer__name='Musa', user=self.user).last()
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.subtotal, Decimal('5000.00'))
        self.assertEqual(invoice.invoiceitem_set.first().product.name, 'Rice')

        # 4. No customer (default Walk-in): "Rice 5k"
        response = self.client.post(reverse('core:smart_input_processor'), {
            'smart_text': 'Rice 5k'
        })
        self.assertIn(response.status_code, [200, 302])
        invoice = Invoice.objects.filter(customer__name='Walk-in Customer', user=self.user).first()
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.subtotal, Decimal('5000.00'))

        # 5. Invalid format: "InvalidText" (should fail parsing, return error message)
        response = self.client.post(reverse('core:smart_input_processor'), {
            'smart_text': 'InvalidText'
        })
        # Should redirect back to dashboard
        self.assertIn(response.status_code, [200, 302])
        # Verify no invoice was created for this
        self.assertFalse(Invoice.objects.filter(subtotal=Decimal('0.00')).exists())

    def test_guest_pdf_watermark_vs_normal(self):
        # 1. Registered user's invoice PDF download (should not have watermark)
        invoice = Invoice.objects.create(
            user=self.user,
            customer=self.customer,
            subtotal=100.00
        )
        response = self.client.get(reverse('core:public_invoice_pdf', args=[invoice.public_token]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

        # 2. Guest trial invoice PDF download (should have watermark)
        guest_customer = Customer.objects.create(name="Guest Cust", phone_number="123")
        guest_invoice = Invoice.objects.create(
            user=None,
            customer=guest_customer,
            subtotal=50.00
        )
        response_guest = self.client.get(reverse('core:public_invoice_pdf', args=[guest_invoice.public_token]))
        self.assertEqual(response_guest.status_code, 200)
        self.assertEqual(response_guest['Content-Type'], 'application/pdf')


