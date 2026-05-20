from django import forms
from .models import Invoice, Customer, Product, Profile

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['business_name', 'industry', 'phone_number', 'address', 'tin', 'profile_picture', 'logo', 'invoice_template', 'primary_products', 'contact_email']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'primary_products': forms.Textarea(attrs={'rows': 2, 'placeholder': 'e.g. Rice, Beans, Garri'}),
        }

class InvoiceForm(forms.ModelForm):
    customer_name = forms.CharField(max_length=255, required=True, label="Customer Name")
    product_name = forms.CharField(max_length=255, required=True, label="Product / Service Name")
    quantity = forms.IntegerField(min_value=1, initial=1, required=True, label="Quantity")

    class Meta:
        model = Invoice
        fields = ['issue_date', 'expected_pay_date', 'subtotal', 'amount_paid', 'status']
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date'}),
            'expected_pay_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['customer_name'].initial = self.instance.customer.name
            first_item = self.instance.invoiceitem_set.first()
            if first_item:
                self.fields['product_name'].initial = first_item.product.name
                self.fields['quantity'].initial = first_item.quantity


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'phone_number', 'email', 'address', 'tin']

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'retail_price', 'wholesale_price', 'stock_quantity']
