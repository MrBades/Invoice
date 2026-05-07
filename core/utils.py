import re
from decimal import Decimal

def parse_smart_input(text):
    """
    Parses strings like 'Bread 500 to Musa'
    Returns: {'product_name': 'Bread', 'amount': 500.0, 'customer_name': 'Musa'}
    """
    # Simple regex pattern: [Product] [Amount] to [Customer]
    # Case insensitive
    pattern = r"(.+?)\s+(\d+)\s+to\s+(.+)"
    match = re.match(pattern, text, re.IGNORECASE)

    if match:
        return {
            'product_name': match.group(1).strip(),
            'amount': Decimal(match.group(2)),
            'customer_name': match.group(3).strip()
        }
    return None
