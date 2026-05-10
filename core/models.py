from django.db import models
import uuid
import random
import string
from django.utils import timezone
from decimal import Decimal

class Customer(models.Model):
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True)
    tin = models.CharField(max_length=50, blank=True, null=True, verbose_name="Tax Identification Number")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def total_debt(self):
        invoiced = self.invoice_set.aggregate(total=models.Sum('total_amount'))['total'] or 0
        paid = self.invoice_set.aggregate(total=models.Sum('amount_paid'))['total'] or 0
        return invoiced - paid

    @property
    def average_days_to_pay(self):
        # Mock calculation for Nigerian MSME trust score
        paid_invoices = self.invoice_set.filter(status='Paid')
        if not paid_invoices:
            return None
        return random.randint(3, 25) # Mocking for demo

class Product(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    retail_price = models.DecimalField(max_digits=12, decimal_places=2)
    wholesale_price = models.DecimalField(max_digits=12, decimal_places=2)
    stock_quantity = models.PositiveIntegerField(default=0)
    target_stock = models.PositiveIntegerField(default=100, help_text="Reference level for 30% low stock alerts")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Invoice(models.Model):
    STATUS_CHOICES = [
        ('Draft', 'Draft'),
        ('Cleared', 'Cleared'),
        ('Overdue', 'Overdue'),
        ('Paid', 'Paid'),
    ]

    invoice_number = models.CharField(max_length=50, unique=True, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    issue_date = models.DateField(default=timezone.now)
    expected_pay_date = models.DateField(blank=True, null=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Draft')
    nrs_irn = models.CharField(max_length=100, blank=True, null=True, verbose_name="FIRS NRS IRN")
    clearance_status = models.CharField(max_length=50, default='Pending')
    public_token = models.UUIDField(default=uuid.uuid4, editable=False)
    is_gbese = models.BooleanField(default=False, verbose_name="Outstanding Debt")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            year = timezone.now().year
            last_invoice = Invoice.objects.filter(invoice_number__contains=f'YB-{year}').order_by('id').last()
            if last_invoice:
                last_num = int(last_invoice.invoice_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            self.invoice_number = f"YB-{year}-{new_num:04d}"

        # Ensure subtotal is Decimal
        self.subtotal = Decimal(str(self.subtotal))

        # Auto-calculate VAT (7.5%) and Total
        self.vat_amount = self.subtotal * Decimal('0.075')
        self.total_amount = self.subtotal + self.vat_amount

        # Auto-mark as Gbese if not fully paid
        self.is_gbese = self.amount_paid < self.total_amount

        super().save(*args, **kwargs)

    def __str__(self):
        return self.invoice_number

class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)

    def save(self, *args, **kwargs):
        self.total_price = Decimal(self.quantity) * Decimal(self.unit_price)
        super().save(*args, **kwargs)

class Notification(models.Model):
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.message[:50]
