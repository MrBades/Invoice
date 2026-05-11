from django import forms
from .models import Invoice, Customer, Product, Profile

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['business_name', 'phone_number', 'address', 'tin', 'profile_picture', 'logo']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }

class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['customer', 'issue_date', 'expected_pay_date', 'subtotal', 'amount_paid', 'status']
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date'}),
            'expected_pay_date': forms.DateInput(attrs={'type': 'date'}),
        }

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'phone_number', 'email', 'address', 'tin']

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'retail_price', 'wholesale_price', 'stock_quantity']
