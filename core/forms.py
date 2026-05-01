from django import forms
from .models import Invoice, Customer, Product

class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['customer', 'issue_date', 'expected_pay_date', 'subtotal', 'status', 'draft_image', 'voice_record']
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date'}),
            'expected_pay_date': forms.DateInput(attrs={'type': 'date'}),
        }

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'phone_number', 'email', 'tin']

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'retail_price', 'wholesale_price', 'stock_quantity']
