import re
from decimal import Decimal

def _build_result(product_name, raw_amount, customer_name):
    raw_amount = raw_amount.lower()
    if raw_amount.endswith('k'):
        amount = Decimal(raw_amount[:-1]) * 1000
    else:
        amount = Decimal(raw_amount)
    return {
        'product_name': product_name.strip(),
        'amount': amount,
        'customer_name': customer_name.strip()
    }

def parse_smart_input(text):
    """
    Parses dynamic shorthand text inputs into structured data dictionaries.
    Supports four highly versatile shorthand patterns:
    1. [Product] [Amount] to [Customer] / [Product] [Amount] [Customer]  (e.g., 'Rice 5k to Musa', 'Rice 5k Musa')
    2. [Amount] [Product] to [Customer] / [Amount] [Product] [Customer]  (e.g., '5k Rice to Musa', '5k Rice Musa')
    3. [Product] [Amount]  (no customer)  (e.g., 'Rice 5k', 'Bread 500' -> defaults customer to 'Walk-in Customer')
    4. [Amount] [Product]  (no customer)  (e.g., '5k Rice', '500 Bread' -> defaults customer to 'Walk-in Customer')
    """
    text = text.strip()
    if not text:
        return None

    # Pattern 1: [Product] [Amount] to [Customer] (with optional 'to')
    # e.g., 'Rice 5k to Musa', 'Rice 5k Musa'
    p1 = r"^(.+?)\s+(\d+(?:\.\d+)?[kK]?)(?:\s+to)?\s+(.+)$"
    m1 = re.match(p1, text, re.IGNORECASE)
    if m1:
        return _build_result(m1.group(1), m1.group(2), m1.group(3))

    # Pattern 2: [Amount] [Product] to [Customer] (with optional 'to')
    # e.g., '5k Rice to Musa', '5k Rice Musa'
    p2 = r"^(\d+(?:\.\d+)?[kK]?)\s+(.+?)(?:\s+to)?\s+(.+)$"
    m2 = re.match(p2, text, re.IGNORECASE)
    if m2:
        return _build_result(m2.group(2), m2.group(1), m2.group(3))

    # Pattern 3: [Product] [Amount] (no customer)
    # e.g., 'Rice 5k', 'Bread 500'
    p3 = r"^(.+?)\s+(\d+(?:\.\d+)?[kK]?)$"
    m3 = re.match(p3, text, re.IGNORECASE)
    if m3:
        return _build_result(m3.group(1), m3.group(2), "Walk-in Customer")

    # Pattern 4: [Amount] [Product] (no customer)
    # e.g., '5k Rice', '500 Bread'
    p4 = r"^(\d+(?:\.\d+)?[kK]?)\s+(.+)$"
    m4 = re.match(p4, text, re.IGNORECASE)
    if m4:
        return _build_result(m4.group(2), m4.group(1), "Walk-in Customer")

    return None
