from django.shortcuts import render, redirect, get_object_or_404
import urllib.parse
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
import random
import string
from django.db.models import Sum, Count
from .models import Invoice, Customer, Product
from .forms import InvoiceForm, CustomerForm, ProductForm

def dashboard(request):
    # Aggregated stats
    total_invoiced = Invoice.objects.aggregate(total=Sum('total_amount'))['total'] or 0
    total_paid = Invoice.objects.aggregate(total=Sum('amount_paid'))['total'] or 0
    total_debt = total_invoiced - total_paid
    
    customer_count = Customer.objects.count()
    
    # FIRS Clearance Rate
    total_invoices = Invoice.objects.count()
    cleared_invoices = Invoice.objects.filter(clearance_status='Success').count()
    clearance_rate = (cleared_invoices / total_invoices * 100) if total_invoices > 0 else 0
    
    recent_invoices = Invoice.objects.all().order_by('-created_at')[:5]
    
    context = {
        'total_invoiced': f"{total_invoiced:,.2f}",
        'total_debt': f"{total_debt:,.2f}",
        'customer_count': customer_count,
        'clearance_rate': round(clearance_rate, 1),
        'recent_invoices': recent_invoices,
    }
    
    return render(request, 'core/dashboard.html', context)

def invoice_list(request):
    invoices = Invoice.objects.all().order_by('-created_at')
    return render(request, 'core/invoice_list.html', {'invoices': invoices})


def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    
    # Construct share links
    customer_name = invoice.customer.name
    invoice_num = invoice.invoice_number
    total = f"N{invoice.total_amount:,.2f}"
    
    # WhatsApp: Format phone number (remove + and spaces)
    phone = invoice.customer.phone_number.replace('+', '').replace(' ', '').replace('-', '')
    wa_msg = f"Hello {customer_name}, here is your invoice {invoice_num} from Yeedem Books. Total: {total}. Thank you for your business!"
    wa_url = f"https://wa.me/{phone}?text={urllib.parse.quote(wa_msg)}"
    
    # Email
    email_subject = f"Invoice {invoice_num} from Yeedem Books"
    email_body = f"Hello {customer_name},\n\nPlease find your invoice {invoice_num} for {total}.\n\nThank you for your business!"
    email_url = f"mailto:{invoice.customer.email or ''}?subject={urllib.parse.quote(email_subject)}&body={urllib.parse.quote(email_body)}"
    
    context = {
        'invoice': invoice,
        'wa_url': wa_url,
        'email_url': email_url,
    }
    return render(request, 'core/invoice_detail.html', context)

def invoice_create(request):
    if request.method == 'POST':
        form = InvoiceForm(request.POST, request.FILES)
        if form.is_valid():
            invoice = form.save(commit=False)
            # Auto-calculate VAT (7.5%) as per Nigerian standards
            invoice.vat_amount = float(invoice.subtotal) * 0.075
            invoice.total_amount = float(invoice.subtotal) + invoice.vat_amount
            invoice.save()
            return redirect('core:invoice_detail', pk=invoice.pk)
    else:
        form = InvoiceForm()
    
    return render(request, 'core/invoice_create.html', {'form': form, 'title': 'Create New Invoice'})

def invoice_edit(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == 'POST':
        form = InvoiceForm(request.POST, request.FILES, instance=invoice)
        if form.is_valid():
            invoice = form.save(commit=False)
            invoice.vat_amount = float(invoice.subtotal) * 0.075
            invoice.total_amount = float(invoice.subtotal) + invoice.vat_amount
            invoice.save()
            return redirect('core:invoice_detail', pk=invoice.pk)
    else:
        form = InvoiceForm(instance=invoice)
    return render(request, 'core/invoice_create.html', {'form': form, 'title': f'Edit Invoice {invoice.invoice_number}'})

def invoice_pdf(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    template_path = 'core/invoice_pdf.html'
    context = {'invoice': invoice}
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Invoice_{invoice.invoice_number}.pdf"'
    template = get_template(template_path)
    html = template.render(context)
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
       return HttpResponse(f'Error generating PDF: {pisa_status.err}')
    return response

def clear_invoice_firs(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    # Mock FIRS Clearance process
    irn = "NRS-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
    invoice.nrs_irn = irn
    invoice.clearance_status = 'Success'
    invoice.status = 'Cleared'
    invoice.save()
    return redirect('core:invoice_detail', pk=pk)

def customer_list(request):
    customers = Customer.objects.all().order_by('-created_at')
    return render(request, 'core/customer_list.html', {'customers': customers})

def customer_create(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('core:customer_list')
    else:
        form = CustomerForm()
    return render(request, 'core/invoice_create.html', {'form': form, 'title': 'Add New Customer'})

def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            return redirect('core:customer_list')
    else:
        form = CustomerForm(instance=customer)
    return render(request, 'core/invoice_create.html', {'form': form, 'title': f'Edit Customer: {customer.name}'})

def product_list(request):
    products = Product.objects.all().order_by('-created_at')
    return render(request, 'core/product_list.html', {'products': products})

def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('core:product_list')
    else:
        form = ProductForm()
    return render(request, 'core/invoice_create.html', {'form': form, 'title': 'Add New Product'})

def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            return redirect('core:product_list')
    else:
        form = ProductForm(instance=product)
    return render(request, 'core/invoice_create.html', {'form': form, 'title': f'Edit Product: {product.name}'})
