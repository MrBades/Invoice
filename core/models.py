from django.db import models
from django.utils import timezone

class Customer(models.Model):
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20, help_text="Formatted for WhatsApp routing")
    email = models.EmailField(max_length=255, blank=True, null=True)
    tin = models.CharField(max_length=50, blank=True, null=True, help_text="FIRS requirement for B2B")
    trust_score = models.IntegerField(default=100, help_text="Default 100 - goes down with late payments")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - Score: {self.trust_score}"

class Product(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    retail_price = models.DecimalField(max_digits=10, decimal_places=2)
    wholesale_price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.IntegerField(default=0, help_text="For inventory alerts")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Invoice(models.Model):
    CLEARANCE_CHOICES = [
        ('Pending', 'Pending'),
        ('Success', 'Success'),
        ('Failed', 'Failed'),
    ]
    STATUS_CHOICES = [
        ('Draft', 'Draft'),
        ('Cleared', 'Cleared'),
        ('Paid', 'Paid'),
        ('Partial', 'Partial'),
        ('Overdue', 'Overdue'),
        ('Cancelled', 'Cancelled'),
    ]

    invoice_number = models.CharField(max_length=50, unique=True, blank=True, help_text="Auto-generated if left blank (e.g., YB-2026-0001)")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='invoices')
    issue_date = models.DateField()
    expected_pay_date = models.DateField(blank=True, null=True)
    
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text="Auto-calculated at 7.5%")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text="Tracks partial/Gbese payments")
    
    # Media Records
    draft_image = models.ImageField(upload_to='invoices/drafts/', blank=True, null=True)
    voice_record = models.FileField(upload_to='invoices/voice/', blank=True, null=True)

    nrs_irn = models.CharField(max_length=100, blank=True, null=True, help_text="FIRS Invoice Reference Number")
    qr_code_url = models.URLField(blank=True, null=True)
    clearance_status = models.CharField(max_length=20, choices=CLEARANCE_CHOICES, default='Pending')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Draft')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            year = timezone.now().year
            last_invoice = Invoice.objects.filter(invoice_number__contains=f"YB-{year}").order_by('-id').first()
            if last_invoice:
                last_number = int(last_invoice.invoice_number.split('-')[-1])
                new_number = f"YB-{year}-{str(last_number + 1).zfill(4)}"
            else:
                new_number = f"YB-{year}-0001"
            self.invoice_number = new_number
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.invoice_number} - {self.customer.name}"

class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Handles wholesale/retail difference at time of sale")
    total_price = models.DecimalField(max_digits=12, decimal_places=2)

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity} x {self.product.name} on {self.invoice.invoice_number}"

class Payment(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateField(auto_now_add=True)
    method = models.CharField(max_length=50)

    def __str__(self):
        return f"Payment of {self.amount} for {self.invoice.invoice_number}"
