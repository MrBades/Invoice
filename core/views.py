from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
import urllib.parse
from django.http import HttpResponse
from django.template.loader import get_template
import random
import string
from django.db.models import Sum, Count
from .models import Invoice, Customer, Product, InvoiceItem, Notification, Profile
from .forms import InvoiceForm, CustomerForm, ProductForm, ProfileForm
from .utils import parse_smart_input
from django.utils import timezone
from decimal import Decimal
from django.contrib import messages

from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login

def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            
            # Transfer guest invoices
            guest_ids = request.session.get('guest_invoice_ids', [])
            if guest_ids:
                Invoice.objects.filter(id__in=guest_ids).update(user=user)
                # Also link customers if any were created as guest
                Customer.objects.filter(invoice__id__in=guest_ids).update(user=user)
                # And products
                Product.objects.filter(invoiceitem__invoice__id__in=guest_ids).update(user=user)
                
                # Clear session
                del request.session['guest_invoice_ids']
                return redirect('core:dashboard') # Skip onboarding if they already made invoices

            return redirect('core:onboarding')
    else:
        form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})

@login_required
def profile_settings(request):
    profile, created = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully!")
            return redirect('core:profile_settings')
    else:
        form = ProfileForm(instance=profile)
    
    return render(request, 'core/profile_settings.html', {'form': form})

def smart_input_processor(request):
    if request.method == 'POST':
        smart_text = request.POST.get('smart_text', '')
        parsed_data = parse_smart_input(smart_text)

        if parsed_data:
            intent = parsed_data.get('intent', 'invoice')

            if intent == 'query' and request.user.is_authenticated:
                query_type = parsed_data.get('query_type')
                query_text = parsed_data.get('text')

                # Logic to answer business queries
                invoices = Invoice.objects.filter(user=request.user)
                if query_type == 'sales_total':
                    total = invoices.aggregate(total=Sum('total_amount'))['total'] or 0
                    msg = f"Your total sales to date is ₦{total:,.2f}."
                elif query_type == 'debt_top':
                    top_debtor = Customer.objects.filter(user=request.user).annotate(
                        debt=Sum('invoice__total_amount') - Sum('invoice__amount_paid')
                    ).order_by('-debt').first()
                    if top_debtor and top_debtor.debt and top_debtor.debt > 0:
                        msg = f"Your top debtor is {top_debtor.name}, owing ₦{top_debtor.debt:,.2f}."
                    else:
                        msg = "You have no outstanding debts from customers!"
                else:
                    # Generic AI advice for other queries
                    from .utils import get_ai_business_insights
                    total_sales = invoices.aggregate(total=Sum('total_amount'))['total'] or 0
                    total_debt = total_sales - (invoices.aggregate(total=Sum('amount_paid'))['total'] or 0)
                    msg = get_ai_business_insights(total_sales, total_debt)

                messages.info(request, f"YB AI: {msg}")
                url = reverse('core:dashboard')
                if request.headers.get('HX-Request'):
                    response = HttpResponse("")
                    response['HX-Redirect'] = url
                    return response
                return redirect(url)

            # Check guest limit
            if not request.user.is_authenticated:
                guest_ids = request.session.get('guest_invoice_ids', [])
                if len(guest_ids) >= 2:
                    if request.headers.get('HX-Request'):
                        response = HttpResponse("")
                        response['HX-Redirect'] = reverse('core:signup')
                        return response
                    return redirect('core:signup')

            # Try to find customer
            cust_filter = {'user': request.user} if request.user.is_authenticated else {'user': None}
            phone = parsed_data.get('customer_phone', '00000000000') or '00000000000'
            customer, _ = Customer.objects.get_or_create(
                name=parsed_data['customer_name'],
                **cust_filter,
                defaults={'phone_number': phone}
            )

            # Try to find product
            prod_filter = {'user': request.user} if request.user.is_authenticated else {'user': None}
            product = Product.objects.filter(name__icontains=parsed_data['product_name'], **prod_filter).first()
            
            quantity = parsed_data.get('quantity', 1)
            subtotal = parsed_data['amount']
            unit_price = subtotal / Decimal(str(quantity)) if quantity > 0 else Decimal('0.00')

            if not product:
                product = Product.objects.create(
                    name=parsed_data['product_name'],
                    retail_price=unit_price,
                    wholesale_price=unit_price,
                    **prod_filter
                )

            # Create Invoice
            invoice = Invoice.objects.create(
                user=request.user if request.user.is_authenticated else None,
                customer=customer,
                issue_date=timezone.now().date(),
                subtotal=subtotal,
                amount_paid=parsed_data.get('amount_paid', Decimal('0.00')),
                status='Draft'
            )

            # Track for guests
            if not request.user.is_authenticated:
                guest_ids = request.session.get('guest_invoice_ids', [])
                guest_ids.append(invoice.id)
                request.session['guest_invoice_ids'] = guest_ids

            # Create Invoice Items
            items = parsed_data.get('items')
            if items:
                # Remove placeholder if it exists (though subtotal is handled by invoice)
                invoice.invoiceitem_set.all().delete()

                for item in items:
                    p_name = item.get('product_name', 'General Goods')
                    p_qty = int(item.get('quantity', 1))
                    p_unit = Decimal(str(item.get('unit_price', 0)))
                    p_total = Decimal(str(item.get('total_price', 0)))

                    if p_unit == 0 and p_total > 0 and p_qty > 0:
                        p_unit = p_total / p_qty

                    # Try to find/create product
                    prod, _ = Product.objects.get_or_create(
                        name=p_name,
                        **prod_filter,
                        defaults={'retail_price': p_unit, 'wholesale_price': p_unit}
                    )

                    InvoiceItem.objects.create(
                        invoice=invoice,
                        product=prod,
                        quantity=p_qty,
                        unit_price=p_unit,
                        total_price=p_total or (p_qty * p_unit)
                    )
            else:
                # Fallback to single item legacy logic
                InvoiceItem.objects.create(
                    invoice=invoice,
                    product=product,
                    quantity=quantity,
                    unit_price=unit_price,
                    total_price=subtotal
                )

            messages.success(request, f"Invoice #{invoice.invoice_number} successfully generated via YB AI!")

            if request.headers.get('HX-Request'):
                url = reverse('core:invoice_detail', args=[invoice.pk]) if request.user.is_authenticated else reverse('core:public_invoice_detail', args=[invoice.public_token])
                response = HttpResponse("")
                response['HX-Redirect'] = url
                return response

            if not request.user.is_authenticated:
                return redirect('core:public_invoice_detail', token=invoice.public_token)
            return redirect('core:invoice_detail', pk=invoice.pk)
        else:
            messages.error(request, "YB AI could not parse the text. Please use format like: 'Rice 5k to Musa' or 'Rice 5k'.")
            
    url = reverse('core:dashboard') if request.user.is_authenticated else reverse('core:landing_page')
    if request.headers.get('HX-Request'):
        response = HttpResponse("")
        response['HX-Redirect'] = url
        return response
    return redirect(url)

def landing_page(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard')
        
    guest_ids = request.session.get('guest_invoice_ids', [])
    invoices = Invoice.objects.filter(id__in=guest_ids)
    
    total_invoiced = invoices.aggregate(total=Sum('total_amount'))['total'] or 0
    total_paid = invoices.aggregate(total=Sum('amount_paid'))['total'] or 0
    total_debt = total_invoiced - total_paid
    
    recent_invoices = invoices.order_by('-created_at')[:5]
    
    context = {
        'total_invoiced': f"{total_invoiced:,.2f}",
        'total_debt': f"{total_debt:,.2f}",
        'recent_invoices': recent_invoices,
        'is_guest': True,
    }
    
    return render(request, 'core/landing_page.html', context)

@login_required
def dashboard(request):
    invoices = Invoice.objects.filter(user=request.user)
    customers = Customer.objects.filter(user=request.user)

    # Aggregated stats
    total_invoiced = invoices.aggregate(total=Sum('total_amount'))['total'] or 0
    total_paid = invoices.aggregate(total=Sum('amount_paid'))['total'] or 0
    total_debt = total_invoiced - total_paid
    
    customer_count = customers.count() if request.user.is_authenticated else 0
    
    # FIRS Clearance Rate
    total_invoices_count = invoices.count()
    cleared_invoices = invoices.filter(clearance_status='Success').count()
    clearance_rate = (cleared_invoices / total_invoices_count * 100) if total_invoices_count > 0 else 0
    
    recent_invoices = invoices.order_by('-created_at')[:5]
    
    context = {
        'total_invoiced': f"{total_invoiced:,.2f}",
        'total_debt': f"{total_debt:,.2f}",
        'total_sales_sum': f"{total_invoiced:,.0f}",
        'total_paid_sum': f"{total_paid:,.0f}",
        'total_debt_sum': f"{total_debt:,.0f}",
        'customer_count': customer_count,
        'clearance_rate': round(clearance_rate, 1),
        'recent_invoices': recent_invoices,
        'is_guest': False,
    }
    
    return render(request, 'core/dashboard.html', context)

@login_required
def invoice_list(request):
    invoices = Invoice.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'core/invoice_list.html', {'invoices': invoices})


def public_invoice_detail(request, token):
    invoice = get_object_or_404(Invoice, public_token=token)
    return render(request, 'core/public_invoice_detail.html', {'invoice': invoice})

@login_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk, user=request.user)
    
    public_link = request.build_absolute_uri(reverse('core:public_invoice_detail', args=[invoice.public_token]))
    customer_name = invoice.customer.name
    invoice_num = invoice.invoice_number
    total = f"N{invoice.total_amount:,.2f}"
    
    # WhatsApp: Format phone number (remove + and spaces)
    phone = invoice.customer.phone_number.replace('+', '').replace(' ', '').replace('-', '')
    wa_msg = f"Hello {customer_name}, here is your invoice {invoice_num} from Yeedem Books. View details here: {public_link}. Total: {total}. Thank you for your business!"
    wa_url = f"https://wa.me/{phone}?text={urllib.parse.quote(wa_msg)}"
    
    # Email
    email_subject = f"Invoice {invoice_num} from Yeedem Books"
    email_body = f"Hello {customer_name},\n\nPlease find your invoice {invoice_num} for {total}.\n\nYou can view/download it at: {public_link}\n\nThank you for your business!"
    email_url = f"mailto:{invoice.customer.email or ''}?subject={urllib.parse.quote(email_subject)}&body={urllib.parse.quote(email_body)}"
    
    context = {
        'invoice': invoice,
        'wa_url': wa_url,
        'email_url': email_url,
        'public_link': public_link,
    }
    return render(request, 'core/invoice_detail.html', context)

@login_required
def invoice_create(request):
    top_products = Product.objects.filter(user=request.user).annotate(sales_count=Count('invoiceitem')).order_by('-sales_count')[:6]
    customers = Customer.objects.filter(user=request.user).order_by('name')
    products = Product.objects.filter(user=request.user).order_by('name')

    if request.method == 'POST':
        form = InvoiceForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            invoice = form.save(commit=False)
            invoice.user = request.user
            
            cust_name = form.cleaned_data['customer_name']
            customer, _ = Customer.objects.get_or_create(
                name=cust_name,
                user=request.user,
                defaults={'phone_number': '00000000000'}
            )
            invoice.customer = customer
            invoice.save()

            prod_name = form.cleaned_data['product_name']
            quantity = form.cleaned_data['quantity']
            unit_price = invoice.subtotal / Decimal(str(quantity)) if quantity > 0 else Decimal('0.00')

            product = Product.objects.filter(name__icontains=prod_name, user=request.user).first()
            if not product:
                product = Product.objects.create(
                    name=prod_name,
                    retail_price=unit_price,
                    wholesale_price=unit_price,
                    user=request.user
                )

            InvoiceItem.objects.create(
                invoice=invoice,
                product=product,
                quantity=quantity,
                unit_price=unit_price,
                total_price=invoice.subtotal
            )

            return redirect('core:invoice_detail', pk=invoice.pk)
    else:
        form = InvoiceForm(user=request.user)
    
    return render(request, 'core/invoice_create.html', {
        'form': form,
        'title': 'Create New Invoice',
        'top_products': top_products,
        'customers': customers,
        'products': products,
    })

@login_required
def invoice_edit(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk, user=request.user)
    top_products = Product.objects.filter(user=request.user).annotate(sales_count=Count('invoiceitem')).order_by('-sales_count')[:6]
    customers = Customer.objects.filter(user=request.user).order_by('name')
    products = Product.objects.filter(user=request.user).order_by('name')

    if request.method == 'POST':
        form = InvoiceForm(request.POST, request.FILES, instance=invoice, user=request.user)
        if form.is_valid():
            invoice = form.save(commit=False)
            
            cust_name = form.cleaned_data['customer_name']
            customer, _ = Customer.objects.get_or_create(
                name=cust_name,
                user=request.user,
                defaults={'phone_number': '00000000000'}
            )
            invoice.customer = customer
            invoice.save()

            prod_name = form.cleaned_data['product_name']
            quantity = form.cleaned_data['quantity']
            unit_price = invoice.subtotal / Decimal(str(quantity)) if quantity > 0 else Decimal('0.00')

            product = Product.objects.filter(name__icontains=prod_name, user=request.user).first()
            if not product:
                product = Product.objects.create(
                    name=prod_name,
                    retail_price=unit_price,
                    wholesale_price=unit_price,
                    user=request.user
                )

            invoice.invoiceitem_set.all().delete()
            InvoiceItem.objects.create(
                invoice=invoice,
                product=product,
                quantity=quantity,
                unit_price=unit_price,
                total_price=invoice.subtotal
            )

            return redirect('core:invoice_detail', pk=invoice.pk)
    else:
        form = InvoiceForm(instance=invoice, user=request.user)
    return render(request, 'core/invoice_create.html', {
        'form': form,
        'title': f'Edit Invoice {invoice.invoice_number}',
        'top_products': top_products,
        'customers': customers,
        'products': products,
    })

def generate_invoice_pdf_response(request, invoice, watermark=False):
    from fpdf import FPDF
    import io

    template = 'classic'
    if request.user.is_authenticated:
        template = request.user.profile.invoice_template

    # Create instance of FPDF class
    pdf = FPDF()
    pdf.add_page()
    
    if watermark:
        with pdf.local_context(fill_opacity=0.12):
            pdf.set_font("Helvetica", 'B', 40)
            pdf.set_text_color(200, 200, 200) # Light gray
            x = 40
            y = 140
            with pdf.rotation(45, x, y):
                pdf.text(x, y, "YEEDEM TRIAL VERSION")

    pdf.set_font("Helvetica", size=12)

    # Header
    pdf.set_font("Helvetica", 'B', 16)
    if template == 'modern':
        pdf.set_text_color(51, 204, 255) # Cyan
    elif template == 'minimalist':
        pdf.set_text_color(31, 41, 55) # Dark Gray
    else:
        pdf.set_text_color(16, 185, 129) # Emerald Green

    biz_name = "Yeedem Books"
    if request.user.is_authenticated:
        biz_name = request.user.profile.business_name or "Yeedem Books"

    pdf.cell(0, 10, biz_name, ln=True)
    pdf.set_font("Helvetica", size=10)
    pdf.set_text_color(102, 102, 102)
    pdf.cell(0, 5, "Lagos, Nigeria", ln=True)
    pdf.cell(0, 5, "TIN: 12345678-0001", ln=True)

    pdf.ln(10)

    # Invoice Title
    pdf.set_font("Helvetica", 'B', 24)
    if template == 'modern':
        pdf.set_text_color(51, 204, 255)
    elif template == 'minimalist':
        pdf.set_text_color(31, 41, 55)
    else:
        pdf.set_text_color(16, 185, 129)
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
    items = list(invoice.invoiceitem_set.all())
    if items:
        for item in items:
            desc = item.product.name
            if item.quantity > 1:
                desc += f" ({item.quantity} x N{item.unit_price:,.2f})"
            pdf.cell(140, 10, desc, border=1)
            pdf.cell(50, 10, f"N{item.total_price:,.2f}", border=1, align='R')
            pdf.ln()
    else:
        pdf.cell(140, 10, "General Services / Products", border=1)
        pdf.cell(50, 10, f"N{invoice.subtotal:,.2f}", border=1, align='R')
        pdf.ln()
    pdf.ln(10)

    # Totals
    pdf.set_x(120)
    pdf.cell(40, 8, "Subtotal:")
    pdf.cell(30, 8, f"N{invoice.subtotal:,.2f}", align='R', ln=True)

    pdf.set_x(120)
    pdf.cell(40, 8, "VAT (7.5%):")
    pdf.cell(30, 8, f"N{invoice.vat_amount:,.2f}", align='R', ln=True)

    pdf.set_x(120)
    pdf.set_font("Helvetica", 'B', 12)
    if template == 'modern':
        pdf.set_text_color(51, 204, 255)
    elif template == 'minimalist':
        pdf.set_text_color(31, 41, 55)
    else:
        pdf.set_text_color(16, 185, 129)
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

@login_required
def invoice_pdf(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk, user=request.user)
    return generate_invoice_pdf_response(request, invoice, watermark=False)

def public_invoice_pdf(request, token):
    invoice = get_object_or_404(Invoice, public_token=token)
    watermark = invoice.user is None
    return generate_invoice_pdf_response(request, invoice, watermark=watermark)

@login_required
def quick_customer_create(request):
    if request.method == 'POST':
        name = request.POST.get('quick_name', '').strip()
        phone = request.POST.get('quick_phone', '').strip() or '00000000000'
        if name:
            customer = Customer.objects.create(name=name, phone_number=phone, user=request.user)
            customers = Customer.objects.filter(user=request.user).order_by('name')
            options = []
            options.append('<option value="" disabled>Select Customer</option>')
            for c in customers:
                selected = "selected" if c.id == customer.id else ""
                options.append(f'<option value="{c.id}" {selected}>{c.name}</option>')
            html = f'<select name="customer" required id="id_customer">{"".join(options)}</select>'
            return HttpResponse(html)
    return HttpResponse("Invalid request", status=400)

@login_required
def clear_invoice_firs(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk, user=request.user)
    # Mock FIRS Clearance process
    irn = "NRS-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
    invoice.nrs_irn = irn
    invoice.clearance_status = 'Success'
    invoice.status = 'Cleared'
    invoice.save()
    return redirect('core:invoice_detail', pk=pk)

@login_required
def customer_list(request):
    customers = Customer.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'core/customer_list.html', {'customers': customers})

@login_required
def customer_create(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('core:customer_list')
    else:
        form = CustomerForm()
    return render(request, 'core/invoice_create.html', {'form': form, 'title': 'Add New Customer'})

@login_required
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk, user=request.user)
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            return redirect('core:customer_list')
    else:
        form = CustomerForm(instance=customer)
    return render(request, 'core/invoice_create.html', {'form': form, 'title': f'Edit Customer: {customer.name}'})

@login_required
def product_list(request):
    products = Product.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'core/product_list.html', {'products': products})

@login_required
def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('core:product_list')
    else:
        form = ProductForm()
    return render(request, 'core/invoice_create.html', {'form': form, 'title': 'Add New Product'})

@login_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk, user=request.user)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            return redirect('core:product_list')
    else:
        form = ProductForm(instance=product)
    return render(request, 'core/invoice_create.html', {'form': form, 'title': f'Edit Product: {product.name}'})

@login_required
def unread_notifications_count(request):
    count = Notification.objects.filter(is_read=False).count()
    return HttpResponse(str(count) if count > 0 else "")

@login_required
def notification_list(request):
    notifications = Notification.objects.all().order_by('-created_at')[:20]
    # Mark as read when viewed? For simplicity let's just show them.
    return render(request, 'core/notification_list.html', {'notifications': notifications})

@login_required
def mark_notifications_read(request):
    Notification.objects.filter(is_read=False).update(is_read=True)
    return HttpResponse("")

@login_required
def onboarding(request):
    step = request.GET.get('step', 'welcome')
    profile, created = Profile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        current_step = request.GET.get('step', 'welcome')
        
        if current_step == 'welcome':
            choice = request.POST.get('setup_method', 'ai_setup')
            step = choice
        elif current_step == 'ai_setup':
            desc_text = request.POST.get('business_description', '').strip()
            from core.utils import parse_business_setup
            parsed_data = parse_business_setup(desc_text)
            if parsed_data:
                profile.business_name = parsed_data['business_name']
                profile.industry = parsed_data['industry']
                profile.phone_number = parsed_data['phone_number']
                profile.address = parsed_data['address']
                profile.tin = parsed_data['tin']
                profile.contact_email = parsed_data.get('contact_email', '')
                profile.primary_products = parsed_data.get('primary_products', '')
                profile.save()
            step = 'review'
        elif current_step == 'review' or current_step == 'manual_setup':
            profile.business_name = request.POST.get('business_name', '').strip()
            profile.industry = request.POST.get('industry', 'other').strip()
            profile.phone_number = request.POST.get('phone_number', '').strip()
            profile.address = request.POST.get('address', '').strip()
            profile.tin = request.POST.get('tin', '').strip()
            profile.contact_email = request.POST.get('contact_email', '').strip()
            profile.primary_products = request.POST.get('primary_products', '').strip()
            profile.invoice_template = request.POST.get('invoice_template', 'classic').strip()
            profile.save()
            step = 'complete'
            
        if step == 'complete':
            if request.headers.get('HX-Request'):
                response = HttpResponse("")
                response['HX-Redirect'] = reverse('core:dashboard')
                return response
            return redirect('core:dashboard')

    context = {
        'step': step,
        'profile': profile,
    }
    if request.headers.get('HX-Request') and not request.headers.get('HX-Boosted'):
        return render(request, f'core/fragments/onboarding_{step}.html', context)
    
    return render(request, 'core/onboarding.html', context)

@login_required
def update_customer_contact(request, pk):
    customer = get_object_or_404(Customer, pk=pk, user=request.user)
    if request.method == 'POST':
        phone = request.POST.get('phone_number')
        email = request.POST.get('email')
        if phone is not None:
            customer.phone_number = phone.strip()
        if email is not None:
            customer.email = email.strip()
        customer.save()
        return HttpResponse("Success")
    return HttpResponse("Invalid Method", status=405)

def terms(request):
    return render(request, 'core/terms.html')

def about(request):
    return render(request, 'core/about.html')

from django.utils.html import format_html, escape
from django.utils.safestring import mark_safe

@login_required
def ai_insights_fragment(request):
    invoices = Invoice.objects.filter(user=request.user)
    total_invoiced = invoices.aggregate(total=Sum('total_amount'))['total'] or 0
    total_paid = invoices.aggregate(total=Sum('amount_paid'))['total'] or 0
    total_debt = total_invoiced - total_paid

    from .utils import get_ai_business_insights
    insights = get_ai_business_insights(total_invoiced, total_debt)

    # Escape AI output first to prevent XSS
    escaped_insights = escape(insights)

    # Convert markdown-style bullets to HTML safely
    formatted_insights = escaped_insights.replace('\n- ', mark_safe('<br>• ')).replace('\n* ', mark_safe('<br>• '))
    if formatted_insights.startswith('- '):
        formatted_insights = mark_safe('• ') + formatted_insights[2:]
    elif formatted_insights.startswith('* '):
        formatted_insights = mark_safe('• ') + formatted_insights[2:]

    return render(request, 'core/fragments/ai_insights.html', {
        'insights': mark_safe(formatted_insights)
    })
