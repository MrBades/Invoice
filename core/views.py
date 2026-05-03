from django.shortcuts import render, redirect, get_object_or_404
import urllib.parse
from django.http import HttpResponse
from django.template.loader import get_template
import random
import string
from django.db.models import Sum, Count
from .models import Invoice, Customer, Product, InvoiceItem
from .forms import InvoiceForm, CustomerForm, ProductForm
from .utils import parse_smart_input
from django.utils import timezone
from decimal import Decimal

def smart_input_processor(request):
    if request.method == 'POST':
        smart_text = request.POST.get('smart_text', '')
        parsed_data = parse_smart_input(smart_text)

        if parsed_data:
            # Try to find customer
            customer, _ = Customer.objects.get_or_create(
                name=parsed_data['customer_name'],
                defaults={'phone_number': '00000000000'} # Placeholder
            )

            # Try to find product
            product = Product.objects.filter(name__icontains=parsed_data['product_name']).first()
            if not product:
                product = Product.objects.create(
                    name=parsed_data['product_name'],
                    retail_price=parsed_data['amount'],
                    wholesale_price=parsed_data['amount'],
                )

            # Create Invoice
            invoice = Invoice.objects.create(
                customer=customer,
                issue_date=timezone.now().date(),
                subtotal=parsed_data['amount'],
                vat_amount=parsed_data['amount'] * Decimal('0.075'),
                total_amount=parsed_data['amount'] * Decimal('1.075'),
                status='Draft'
            )

            # Create Invoice Item
            InvoiceItem.objects.create(
                invoice=invoice,
                product=product,
                quantity=1,
                unit_price=parsed_data['amount'],
                total_price=parsed_data['amount']
            )

            return redirect('core:invoice_detail', pk=invoice.pk)

    return redirect('core:dashboard')

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
        'total_sales_sum': f"{total_invoiced:,.0f}",
        'total_paid_sum': f"{total_paid:,.0f}",
        'total_debt_sum': f"{total_debt:,.0f}",
        'customer_count': customer_count,
        'clearance_rate': round(clearance_rate, 1),
        'recent_invoices': recent_invoices,
    }
    
    return render(request, 'core/dashboard.html', context)

def invoice_list(request):
    invoices = Invoice.objects.all().order_by('-created_at')
    return render(request, 'core/invoice_list.html', {'invoices': invoices})


def public_invoice_detail(request, token):
    invoice = get_object_or_404(Invoice, public_token=token)
    return render(request, 'core/public_invoice_detail.html', {'invoice': invoice})

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
    top_products = Product.objects.annotate(sales_count=Count('invoiceitem')).order_by('-sales_count')[:6]

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
    
    return render(request, 'core/invoice_create.html', {
        'form': form,
        'title': 'Create New Invoice',
        'top_products': top_products
    })

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
    from fpdf import FPDF
    import io

    invoice = get_object_or_404(Invoice, pk=pk)

    # Create instance of FPDF class
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)

    # Header
    pdf.set_font("Helvetica", 'B', 16)
    pdf.set_text_color(0, 135, 81) # #008751 (Yeedem Green)
    pdf.cell(0, 10, "Yeedem Books", ln=True)
    pdf.set_font("Helvetica", size=10)
    pdf.set_text_color(102, 102, 102)
    pdf.cell(0, 5, "Lagos, Nigeria", ln=True)
    pdf.cell(0, 5, "TIN: 12345678-0001", ln=True)

    pdf.ln(10)

    # Invoice Title
    pdf.set_font("Helvetica", 'B', 24)
    pdf.set_text_color(0, 135, 81)
    pdf.cell(0, 15, "INVOICE", ln=True, align='R')
    pdf.set_font("Helvetica", size=12)
    pdf.set_text_color(51, 51, 51)
    pdf.cell(0, 10, f"#{invoice.invoice_number}", ln=True, align='R')

    pdf.ln(10)

    # Customer Details
    pdf.set_font("Helvetica", 'B', 10)
    pdf.set_text_color(102, 102, 102)
    pdf.cell(100, 5, "BILL TO", ln=0)
    pdf.cell(0, 5, "DATE ISSUED", ln=1, align='R')

    pdf.set_font("Helvetica", 'B', 12)
    pdf.set_text_color(51, 51, 51)
    pdf.cell(100, 7, invoice.customer.name, ln=0)
    pdf.cell(0, 7, str(invoice.issue_date), ln=1, align='R')

    pdf.set_font("Helvetica", size=10)
    pdf.set_text_color(102, 102, 102)
    pdf.cell(100, 5, invoice.customer.phone_number, ln=0)
    pdf.cell(0, 5, "DUE DATE", ln=1, align='R')

    if invoice.customer.tin:
        pdf.cell(100, 5, f"TIN: {invoice.customer.tin}", ln=0)
    else:
        pdf.cell(100, 5, "", ln=0)
    pdf.set_font("Helvetica", 'B', 10)
    pdf.set_text_color(51, 51, 51)
    pdf.cell(0, 5, str(invoice.expected_pay_date or invoice.issue_date), ln=1, align='R')

    pdf.ln(15)

    # Items Table
    pdf.set_fill_color(248, 249, 250)
    pdf.set_font("Helvetica", 'B', 10)
    pdf.cell(140, 10, "Description", border=1, fill=True)
    pdf.cell(50, 10, "Amount", border=1, fill=True, align='R')
    pdf.ln()

    pdf.set_font("Helvetica", size=10)
    pdf.cell(140, 10, "General Services / Products", border=1)
    pdf.cell(50, 10, f"N{invoice.subtotal:,.2f}", border=1, align='R')
    pdf.ln(20)

    # Totals
    pdf.set_x(120)
    pdf.cell(40, 8, "Subtotal:")
    pdf.cell(30, 8, f"N{invoice.subtotal:,.2f}", align='R', ln=True)

    pdf.set_x(120)
    pdf.cell(40, 8, "VAT (7.5%):")
    pdf.cell(30, 8, f"N{invoice.vat_amount:,.2f}", align='R', ln=True)

    pdf.set_x(120)
    pdf.set_font("Helvetica", 'B', 12)
    pdf.set_text_color(0, 135, 81)
    pdf.cell(40, 10, "Total:")
    pdf.cell(30, 10, f"N{invoice.total_amount:,.2f}", align='R', ln=True)

    pdf.ln(30)

    # Footer
    pdf.set_font("Helvetica", size=10)
    pdf.set_text_color(102, 102, 102)
    pdf.cell(0, 5, f"FIRS NRS Clearance: {invoice.nrs_irn or 'Pending Verification'}", align='C', ln=True)
    pdf.cell(0, 5, "Thank you for your business!", align='C', ln=True)
    pdf.cell(0, 10, "© 2026 Yeedem Books. All rights reserved.", align='C', ln=True)

    # Output the PDF to a buffer
    buffer = io.BytesIO()
    pdf_output = pdf.output()
    if isinstance(pdf_output, str):
        buffer.write(pdf_output.encode('latin-1'))
    else:
        buffer.write(pdf_output)
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Invoice_{invoice.invoice_number}.pdf"'
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
