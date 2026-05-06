from django.db.models import Sum
from .models import Invoice

def daily_truth_context(request):
    """
    Provides global context for the 'Daily Truth' sticky header.
    """
    total_invoiced = Invoice.objects.aggregate(total=Sum('total_amount'))['total'] or 0
    total_paid = Invoice.objects.aggregate(total=Sum('amount_paid'))['total'] or 0
    total_debt = total_invoiced - total_paid

    return {
        'total_sales_sum': f"{total_invoiced:,.0f}",
        'total_paid_sum': f"{total_paid:,.0f}",
        'total_debt_sum': f"{total_debt:,.0f}",
    }
