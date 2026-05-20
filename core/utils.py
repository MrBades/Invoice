import os
import re
import socket
from decimal import Decimal
from pydantic import BaseModel, Field

class SmartInputSchema(BaseModel):
    intent: str = Field(description="The intent of the query: 'invoice' (if a customer bought something or we need to generate an invoice) or 'query' (if a business question, e.g. how much did I sell, who owes, debt).")
    query_type: str = Field(default="general", description="If intent is query, query_type must be: 'sales_total', 'debt_top', or 'general'. Otherwise use 'general'.")
    text: str = Field(default="", description="If intent is query, the original text or business question.")
    product_name: str = Field(default="General Goods", description="If intent is invoice, the name of the product purchased.")
    amount: float = Field(default=0.0, description="If intent is invoice, the transaction amount (total price). Standard amount paid/total cost.")
    customer_name: str = Field(default="Walk-in Customer", description="If intent is invoice, the customer's name.")
    customer_phone: str = Field(default="", description="If intent is invoice, the customer's phone number.")
    amount_paid: float = Field(default=0.0, description="If intent is invoice, the amount paid by the customer so far.")
    quantity: int = Field(default=1, description="If intent is invoice, the quantity of product purchased.")

class BusinessSetupSchema(BaseModel):
    business_name: str = Field(default="My Business", description="The business name.")
    industry: str = Field(default="other", description="Must be one of: 'retail', 'services', 'manufacturing', or 'other'.")
    phone_number: str = Field(default="", description="The business phone number.")
    address: str = Field(default="", description="The business address.")
    tin: str = Field(default="", description="The tax identification number (TIN).")

import ssl
import time

_last_connectivity_check = 0
_is_api_reachable = False

def is_online(timeout=2):
    """Check internet connectivity by attempting an HTTP HEAD request to a lightweight endpoint.
    Uses https://www.gstatic.com/generate_204 which returns a 204 No Content quickly.
    Result is cached for 60 seconds.
    """
    global _last_connectivity_check, _is_api_reachable
    now = time.time()
    if now - _last_connectivity_check < 60:
        return _is_api_reachable
    try:
        import urllib.request
        req = urllib.request.Request('https://www.gstatic.com/generate_204', method='HEAD')
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            _is_api_reachable = resp.status in (200, 204)
    except Exception:
        _is_api_reachable = False
    _last_connectivity_check = now
    return _is_api_reachable

def clean_name(name):
    """Helper to clean extracted names from common prepositions."""
    name = name.strip()
    name = re.sub(r'^(?:for|to|of|bought|bought\s+by|came\s+and|came\s+to|came|and|but)\s+', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+(?:for|to|of|and|but)$', '', name, flags=re.IGNORECASE)
    return name.strip()

def parse_smart_input(text):
    """
    Hybrid Parser:
    1. Check Connectivity.
    2. If Online & API Key exists -> Use Google GenAI SDK (Gemini).
    3. If Offline or API fails -> Use Token-based Heuristic Fallback.
    """
    text = text.strip()
    if not text:
        return None

    api_key = os.environ.get("GEMINI_API_KEY")

    # 1. Try Online AI Parsing if connected
    if api_key and is_online():
        try:
            from google import genai
            from google.genai import types
            import json
            
            # Using http_options to specify a timeout of 10s to optimize for 3G speeds
            client = genai.Client(api_key=api_key, http_options={'timeout': 10})
            model_id = "gemini-2.5-flash"

            prompt = (
                "You are an expert financial parsing assistant for Nigerian MSMEs. Identify the intent and extract structured data.\n"
                "Intents: 'invoice' (transaction) or 'query' (business question).\n"
                "Extract: product_name, customer_name, customer_phone, amount (total price), amount_paid, quantity.\n"
                f"Input text: \"{text}\"\n\n"
                "Rules:\n"
                "- amount: 5k -> 5000.\n"
                "- customer_name: default 'Walk-in Customer'.\n"
                "- quantity: default 1."
            )
            
            response = client.models.generate_content(
                model=model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=SmartInputSchema,
                )
            )
            
            data = json.loads(response.text)
            intent = data.get('intent', 'invoice')
            
            if intent == 'query':
                return {
                    'intent': 'query',
                    'query_type': data.get('query_type', 'general'),
                    'text': data.get('text', text)
                }

            return {
                'intent': 'invoice',
                'product_name': data.get('product_name', 'General Goods') or 'General Goods',
                'amount': Decimal(str(data.get('amount', 0))),
                'customer_name': data.get('customer_name', 'Walk-in Customer') or 'Walk-in Customer',
                'customer_phone': data.get('customer_phone', ''),
                'amount_paid': Decimal(str(data.get('amount_paid', 0))),
                'quantity': int(data.get('quantity', 1))
            }
        except Exception:
            pass

    # 2. Offline Token-based Heuristic Fallback
    return _parse_smart_input_offline(text)


def _parse_smart_input_offline(text):
    text_lower = text.lower()

    # Query detection
    if "total sales" in text_lower or "how much did i sell" in text_lower:
        return {'intent': 'query', 'query_type': 'sales_total', 'text': text}
    if "who owes" in text_lower or "debt" in text_lower:
        return {'intent': 'query', 'query_type': 'debt_top', 'text': text}

    def parse_numeric_val(val_str):
        val_str = val_str.lower().replace(',', '')
        if val_str.endswith('k'):
            try:
                return Decimal(val_str[:-1]) * 1000
            except:
                return Decimal('0')
        try:
            return Decimal(val_str)
        except:
            return Decimal('0')

    # Extract Phone
    phone = ''
    phone_match = re.search(r'\b(?:\+?234|0)\d{9,11}\b', text)
    if phone_match:
        phone = phone_match.group(0)
        text = text.replace(phone, ' ').strip()

    amount_paid = Decimal('0.00')
    # 1. Extract paid amount
    paid_match = re.search(r'\b(?:paid|paying|deposit|advance|payment)(?:\s+of)?\s*(?:₦|n|N)?\s*(\d+(?:[.,]\d+)?\s*[kK]?)\b', text, re.IGNORECASE)
    if paid_match:
        amount_paid = parse_numeric_val(paid_match.group(1))
        text = text[:paid_match.start()] + " " + text[paid_match.end():]
        text = re.sub(r'\s+', ' ', text).strip()

    # 2. Extract transaction amount
    amount = Decimal('0.00')
    amount_match = re.search(r'\b(?:for|at|costing|price|total|value|worth)(?:\s+of)?\s*(?:₦|n|N)?\s*(\d+(?:[.,]\d+)?\s*[kK]?)\b', text, re.IGNORECASE)
    if amount_match:
        amount = parse_numeric_val(amount_match.group(1))
        text = text[:amount_match.start()] + " " + text[amount_match.end():]
        text = re.sub(r'\s+', ' ', text).strip()
    else:
        # Find any standalone number
        all_nums = re.findall(r'\b(\d+(?:[.,]\d+)?\s*[kK]?)\b', text)
        if all_nums:
            price_candidate = None
            for num in all_nums:
                idx = text.find(num)
                after_num = text[idx + len(num):].strip().lower()
                is_quantity = False
                for unit in ['bag', 'pcs', 'piece', 'carton', 'pkt', 'pack', 'item', 'kg', 'liter', 'unit']:
                    if after_num.startswith(unit):
                        is_quantity = True
                        break
                if not is_quantity:
                    price_candidate = num
                    break
            
            if price_candidate:
                amount = parse_numeric_val(price_candidate)
                text = re.sub(r'\b' + re.escape(price_candidate) + r'\b', ' ', text, count=1)
                text = re.sub(r'\s+', ' ', text).strip()

    if amount == Decimal('0.00') and amount_paid > Decimal('0.00'):
        amount = amount_paid

    # 3. Extract quantity
    quantity = 1
    number_words_map = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
    }
    qty_pattern = r'\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s*(?:bags?\s+of|bags?|pcs?|pieces?|cartons?|pkts?|packs?|items?|kg|liters?|units?)\b'
    qty_match = re.search(qty_pattern, text, re.IGNORECASE)
    if qty_match:
        qty_str = qty_match.group(1).lower()
        quantity = number_words_map.get(qty_str, None)
        if quantity is None:
            try:
                quantity = int(qty_str)
            except:
                quantity = 1
        text = text[:qty_match.start()] + " " + text[qty_match.end():]
        text = re.sub(r'\s+', ' ', text).strip()
    else:
        lead_qty_match = re.match(r'^(\d+)\s+([a-zA-Z].*)$', text)
        if lead_qty_match:
            quantity = int(lead_qty_match.group(1))
            text = lead_qty_match.group(2).strip()
        else:
            # Check for standalone number words at the beginning
            lead_word_qty_match = re.match(r'^(one|two|three|four|five|six|seven|eight|nine|ten)\s+([a-zA-Z].*)$', text, re.IGNORECASE)
            if lead_word_qty_match:
                quantity = number_words_map[lead_word_qty_match.group(1).lower()]
                text = lead_word_qty_match.group(2).strip()

    # 4. Customer and Product
    customer_name = "Walk-in Customer"
    product_name = ""

    verb_pattern = r'\b(bought|purchased|took|ordered|wants|got|buys|purchases|takes|buy|came\s+and\s+buy|came\s+to\s+buy|collected?|came\s+and\s+collected?)\b'
    verb_match = re.search(verb_pattern, text, re.IGNORECASE)
    if verb_match:
        cust_part = text[:verb_match.start()].strip()
        prod_part = text[verb_match.end():].strip()
        if cust_part:
            customer_name = clean_name(cust_part)
        if prod_part:
            product_name = clean_name(prod_part)
    else:
        split_match = re.search(r'\b(to|for)\b', text, re.IGNORECASE)
        if split_match:
            prod_part = text[:split_match.start()].strip()
            cust_part = text[split_match.end():].strip()
            if prod_part:
                product_name = clean_name(prod_part)
            if cust_part:
                customer_name = clean_name(cust_part)
        else:
            words = text.split()
            if len(words) >= 2:
                product_name = clean_name(words[0])
                customer_name = clean_name(" ".join(words[1:]))
            elif len(words) == 1:
                product_name = words[0]
            else:
                product_name = "General Goods"

    customer_name = clean_name(customer_name)
    product_name = clean_name(product_name)

    if not product_name: product_name = "General Goods"
    if not customer_name: customer_name = "Walk-in Customer"

    if amount == Decimal('0.00') or not re.search(r'[a-zA-Z]', text):
        return None

    return {
        'intent': 'invoice',
        'product_name': product_name,
        'amount': amount,
        'customer_name': customer_name,
        'customer_phone': phone,
        'amount_paid': amount_paid,
        'quantity': quantity
    }

def parse_business_setup(text):
    """
    Hybrid Business Setup Parser.
    """
    text = text.strip()
    if not text:
        return None

    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key and is_online():
        try:
            from google import genai
            from google.genai import types
            import json
            
            # Using http_options to specify a timeout of 10s to optimize for 3G speeds
            client = genai.Client(api_key=api_key, http_options={'timeout': 10})
            model_id = "gemini-2.5-flash"
            
            prompt = f"Extract business details from this description: '{text}'"
            response = client.models.generate_content(
                model=model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=BusinessSetupSchema,
                )
            )
            data = json.loads(response.text)
            return {
                'business_name': data.get('business_name', 'My Business') or 'My Business',
                'industry': data.get('industry', 'other') or 'other',
                'phone_number': data.get('phone_number', '') or '',
                'address': data.get('address', '') or '',
                'tin': data.get('tin', '') or ''
            }
        except Exception:
            pass

    return _parse_business_setup_offline(text)

def _parse_business_setup_offline(text):
    phone_match = re.search(r'\b(?:\+?234|0)\d{9,11}\b|\+?\d[\d\s-]{8,15}\d', text)
    phone = phone_match.group(0).strip() if phone_match else ''
    
    tin_match = re.search(r'\b\d{8}-\d{4}\b|\b\d{8,12}\b', text)
    tin = tin_match.group(0).strip() if tin_match else ''
    
    industry = 'other'
    text_lower = text.lower()
    retail_kws = ['shop', 'store', 'sell', 'retail', 'boutique', 'supermarket', 'merchant', 'dealer', 'market', 'goods', 'groceries', 'clothes', 'garri', 'rice', 'bread', 'food', 'provision']
    services_kws = ['consulting', 'consultant', 'services', 'agency', 'law', 'legal', 'clinic', 'hospital', 'repair', 'salon', 'barber', 'tech', 'software', 'teaching', 'school', 'design', 'creative', 'mechanic', 'electrician']
    mfg_kws = ['factory', 'manufacturing', 'manufacturer', 'production', 'produce', 'mill', 'plant', 'assembly', 'make', 'builder', 'bakery', 'farm', 'agriculture']
    
    if any(kw in text_lower for kw in retail_kws): industry = 'retail'
    elif any(kw in text_lower for kw in services_kws): industry = 'services'
    elif any(kw in text_lower for kw in mfg_kws): industry = 'manufacturing'

    address = ''
    address_indicators = ['street', 'st', 'road', 'rd', 'way', 'avenue', 'ave', 'lane', 'ln', 'close', 'cl', 'crescent', 'cres', 'highway', 'hwy', 'plaza', 'mall', 'complex', 'lagos', 'abuja', 'ikeja', 'yaba', 'lekki', 'nigeria', 'no.', 'plot', 'suite']
    segments = re.split(r'[,.\n]', text)
    address_parts = [seg.strip() for seg in segments if any(ind in seg.lower() for ind in address_indicators) and len(seg.strip()) > 5]
    if address_parts: address = ', '.join(address_parts)
    
    business_name = 'My Business'
    words = text.split()
    if words:
        capitalized = [w for w in words[:5] if w[0].isupper() and w.lower() not in ['i', 'we', 'my', 'our', 'the', 'a', 'an']]
        if capitalized: business_name = ' '.join(capitalized)
        else: business_name = ' '.join(words[:2])

    return {
        'business_name': re.sub(r'[^\w\s]', '', business_name).strip() or 'My Business',
        'industry': industry,
        'phone_number': phone,
        'address': address,
        'tin': tin
    }

def get_ai_business_insights(sales_data, debt_data, inventory_data=None):
    """
    Generates personalized business insights. Checks connectivity first.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or not is_online():
        return "Connect your Gemini API Key and stay online to unlock personalized AI business insights."

    try:
        from google import genai
        # Using http_options to specify a timeout of 10s to optimize for 3G speeds
        client = genai.Client(api_key=api_key, http_options={'timeout': 10})
        model_id = "gemini-2.5-flash"
        
        prompt = (
            f"As a business consultant for Nigerian MSMEs, analyze: Sales N{sales_data}, Debt N{debt_data}. "
            "Give 3 concise actionable tips. Max 60 words."
        )
        response = client.models.generate_content(model=model_id, contents=prompt)
        return response.text.strip()
    except Exception:
        return "YB AI is currently offline. Check your connection for new insights."
