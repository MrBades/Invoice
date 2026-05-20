from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Customer, Invoice
from decimal import Decimal
from unittest.mock import patch, MagicMock


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

        # 4b. Natural language pattern with quantity and amount paid: "Moses bought 5 bags of garri for 20000 paid 15000"
        response = self.client.post(reverse('core:smart_input_processor'), {
            'smart_text': 'Moses bought 5 bags of garri for 20000 paid 15000'
        })
        self.assertIn(response.status_code, [200, 302])
        invoice = Invoice.objects.filter(customer__name='Moses', user=self.user).first()
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.subtotal, Decimal('20000.00'))
        self.assertEqual(invoice.amount_paid, Decimal('15000.00'))
        self.assertTrue(invoice.is_gbese)
        item = invoice.invoiceitem_set.first()
        self.assertIsNotNone(item)
        self.assertEqual(item.product.name, 'garri')
        self.assertEqual(item.quantity, 5)
        self.assertEqual(item.unit_price, Decimal('4000.00'))
        # 4c. Nigerian shorthand pattern with "for": "beans for pp 5000"
        response = self.client.post(reverse('core:smart_input_processor'), {
            'smart_text': 'beans for pp 5000'
        })
        self.assertIn(response.status_code, [200, 302])
        invoice = Invoice.objects.filter(customer__name='pp', user=self.user).first()
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.subtotal, Decimal('5000.00'))
        item = invoice.invoiceitem_set.first()
        self.assertIsNotNone(item)
        self.assertEqual(item.product.name, 'beans')
        # 5. Invalid format: "InvalidText" (should fail parsing, return error message)
        response = self.client.post(reverse('core:smart_input_processor'), {
            'smart_text': 'InvalidText'
        })
        # Should redirect back to dashboard
        self.assertIn(response.status_code, [200, 302])
        # Verify no invoice was created for this
        self.assertFalse(Invoice.objects.filter(subtotal=Decimal('0.00')).exists())

    @patch('google.genai.Client')
    @patch('core.utils.is_online', return_value=True)
    def test_smart_input_processor_with_ai(self, mock_online, mock_gen_client):
        mock_client_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"items": [{"product_name": "Garri", "total_price": 20000, "quantity": 5, "unit_price": 4000}], "customer_name": "Moses", "amount_paid": 15000, "subtotal": 20000}'
        mock_client_instance.models.generate_content.return_value = mock_response
        mock_gen_client.return_value = mock_client_instance

        with patch.dict('os.environ', {'GEMINI_API_KEY': 'fake_key'}):
            from core.utils import parse_smart_input
            res = parse_smart_input("Moses bought 5 bags of garri for 20000 paid 15000")
            
            self.assertIsNotNone(res)
            self.assertEqual(res['items'][0]['product_name'], 'Garri')
            self.assertEqual(res['subtotal'], Decimal('20000.00'))
            self.assertEqual(res['customer_name'], 'Moses')
            self.assertEqual(res['amount_paid'], Decimal('15000.00'))
            self.assertEqual(res['items'][0]['quantity'], 5)

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

    def test_public_invoice_detail_view(self):
        # 1. Test public detail view for a registered user's invoice
        invoice = Invoice.objects.create(
            user=self.user,
            customer=self.customer,
            subtotal=Decimal('100.00'),
            amount_paid=Decimal('20.00'),
            status='Draft'
        )
        response = self.client.get(reverse('core:public_invoice_detail', args=[invoice.public_token]))
        self.assertEqual(response.status_code, 200)
        self.assertIn('Total Amount', response.content.decode('utf-8'))
        
        # 2. Test public detail view for a guest invoice (user=None)
        guest_customer = Customer.objects.create(name="Guest Cust", phone_number="123")
        guest_invoice = Invoice.objects.create(
            user=None,
            customer=guest_customer,
            subtotal=Decimal('50.00'),
            amount_paid=Decimal('10.00'),
            status='Draft'
        )
        response_guest = self.client.get(reverse('core:public_invoice_detail', args=[guest_invoice.public_token]))
        self.assertEqual(response_guest.status_code, 200)
        self.assertIn('Total Amount', response_guest.content.decode('utf-8'))

    def test_parse_business_setup_heuristics(self):
        from core.utils import parse_business_setup
        text = "Bades Electronics is at 12 Herbert Macaulay Way, Yaba, Lagos. Tel: +2348033333333, TIN is 12345678-0001. We do retail."
        res = parse_business_setup(text)
        self.assertIsNotNone(res)
        self.assertEqual(res['business_name'], 'Bades Electronics')
        self.assertEqual(res['industry'], 'retail')
        self.assertEqual(res['phone_number'], '+2348033333333')
        self.assertEqual(res['tin'], '12345678-0001')
        self.assertIn('12 Herbert Macaulay Way', res['address'])

    @patch('google.genai.Client')
    @patch('core.utils.is_online', return_value=True)
    def test_parse_business_setup_with_ai(self, mock_online, mock_gen_client):
        mock_client_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"business_name": "Bades Electronics", "industry": "retail", "phone_number": "+2348033333333", "address": "12 Herbert Macaulay Way, Yaba, Lagos", "tin": "12345678-0001"}'
        mock_client_instance.models.generate_content.return_value = mock_response
        mock_gen_client.return_value = mock_client_instance

        with patch.dict('os.environ', {'GEMINI_API_KEY': 'fake_key'}):
            from core.utils import parse_business_setup
            res = parse_business_setup("My company description")
            
            self.assertIsNotNone(res)
            self.assertEqual(res['business_name'], 'Bades Electronics')
            self.assertEqual(res['industry'], 'retail')
            self.assertEqual(res['phone_number'], '+2348033333333')
            self.assertEqual(res['address'], '12 Herbert Macaulay Way, Yaba, Lagos')
            self.assertEqual(res['tin'], '12345678-0001')

    def test_onboarding_view_progression(self):
        # 1. Get welcome step
        response = self.client.get(reverse('core:onboarding'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('step', response.context)
        self.assertEqual(response.context['step'], 'welcome')

        # 2. Select manual setup step
        response = self.client.post(reverse('core:onboarding') + '?step=welcome', {'setup_method': 'manual_setup'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['step'], 'manual_setup')

        # 3. Submit manual setup
        response = self.client.post(reverse('core:onboarding') + '?step=manual_setup', {
            'business_name': 'Manual Biz Ltd',
            'industry': 'services',
            'phone_number': '09012345678',
            'address': 'Plot 4, Lekki, Lagos',
            'tin': '98765432-0001'
        })
        self.assertIn(response.status_code, [200, 302])
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.business_name, 'Manual Biz Ltd')
        self.assertEqual(self.user.profile.industry, 'services')
        self.assertEqual(self.user.profile.phone_number, '09012345678')
        self.assertEqual(self.user.profile.address, 'Plot 4, Lekki, Lagos')
        self.assertEqual(self.user.profile.tin, '98765432-0001')

    def test_manual_invoice_creation_and_edit(self):
        # 1. Login user
        self.client.force_login(self.user)

        # 2. POST create invoice
        response = self.client.post(reverse('core:invoice_create'), {
            'customer_name': 'New Customer Co',
            'product_name': 'New Product Item',
            'quantity': 3,
            'issue_date': '2026-05-19',
            'expected_pay_date': '2026-05-25',
            'subtotal': '30000.00',
            'amount_paid': '10000.00',
            'status': 'Draft'
        })
        self.assertEqual(response.status_code, 302)

        # Verify database
        invoice = Invoice.objects.filter(user=self.user, customer__name='New Customer Co').first()
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.subtotal, Decimal('30000.00'))
        self.assertEqual(invoice.amount_paid, Decimal('10000.00'))
        
        # Verify items
        item = invoice.invoiceitem_set.first()
        self.assertIsNotNone(item)
        self.assertEqual(item.product.name, 'New Product Item')
        self.assertEqual(item.quantity, 3)
        self.assertEqual(item.unit_price, Decimal('10000.00'))

        # 3. POST edit invoice
        response = self.client.post(reverse('core:invoice_edit', args=[invoice.pk]), {
            'customer_name': 'Updated Customer Co',
            'product_name': 'Updated Product Item',
            'quantity': 2,
            'issue_date': '2026-05-19',
            'expected_pay_date': '2026-05-25',
            'subtotal': '20000.00',
            'amount_paid': '20000.00',
            'status': 'Paid'
        })
        self.assertEqual(response.status_code, 302)

        # Verify updates
        invoice.refresh_from_db()
        self.assertEqual(invoice.customer.name, 'Updated Customer Co')
        self.assertEqual(invoice.subtotal, Decimal('20000.00'))
        self.assertEqual(invoice.status, 'Paid')
        
        item = invoice.invoiceitem_set.first()
        self.assertIsNotNone(item)
        self.assertEqual(item.product.name, 'Updated Product Item')
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.unit_price, Decimal('10000.00'))
