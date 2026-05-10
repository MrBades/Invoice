import re
from decimal import Decimal

def parse_smart_input(text):
    """
    Parses strings like 'Bread 500 to Musa' or 'Rice 5k to Musa'
    Returns: {'product_name': 'Bread', 'amount': 500.0, 'customer_name': 'Musa'}
    """
    # Regex pattern: [Product] [Amount(k?)] to [Customer]
    # Supports '500', '5k', '5.5k'
    pattern = r"(.+?)\s+(\d+(?:\.\d+)?[kK]?)\s+to\s+(.+)"
    match = re.match(pattern, text, re.IGNORECASE)

    if match:
        raw_amount = match.group(2).lower()
        if raw_amount.endswith('k'):
            amount = Decimal(raw_amount[:-1]) * 1000
        else:
            amount = Decimal(raw_amount)

        return {
            'product_name': match.group(1).strip(),
            'amount': amount,
            'customer_name': match.group(3).strip()
        }
    return None
