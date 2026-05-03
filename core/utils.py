import re
from decimal import Decimal
def parse_smart_input(input_text):
    """
    Parses input like "Rice 5k to Musa"
    Returns a dictionary with product_name, amount, and customer_name
    """
    # Regex to find: <Product> <Amount> to <Customer>
    # Example: "Rice 5k to Musa" or "Beans 2000 to John"

    pattern = r'^(?P<product>.+)\s+(?P<amount>\d+[kK]?)\s+to\s+(?P<customer>.+)$'
    match = re.match(pattern, input_text.strip(), re.IGNORECASE)

    if not match:
        return None

    product_name = match.group('product').strip()
    amount_str = match.group('amount').lower().strip()
    customer_name = match.group('customer').strip()

    if amount_str.endswith('k'):
        amount = Decimal(amount_str[:-1]) * 1000
    else:
        amount = Decimal(amount_str)

    return {
        'product_name': product_name,
        'amount': amount,
        'customer_name': customer_name
    }
