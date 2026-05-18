from django.db.models import Sum
from .models import Invoice

def daily_truth_context(request):
    """
    Provides global context for the 'Daily Truth' sticky header.
    """
    if request.user.is_authenticated:
        invoices = Invoice.objects.filter(user=request.user)
    else:
        guest_ids = request.session.get('guest_invoice_ids', []) if hasattr(request, 'session') else []
        invoices = Invoice.objects.filter(id__in=guest_ids)

    total_invoiced = invoices.aggregate(total=Sum('total_amount'))['total'] or 0
    total_paid = invoices.aggregate(total=Sum('amount_paid'))['total'] or 0
    total_debt = total_invoiced - total_paid

    return {
        'total_sales_sum': f"{total_invoiced:,.0f}",
        'total_paid_sum': f"{total_paid:,.0f}",
        'total_debt_sum': f"{total_debt:,.0f}",
    }

