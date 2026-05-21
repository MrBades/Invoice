import os
import re
import socket
import logging
import json
from decimal import Decimal
from django.conf import settings
from google import genai

logger = logging.getLogger(__name__)

def is_online(timeout=2):
    """
    Checks for active internet connectivity.
    Uses multiple targets and methods to avoid false negatives.
    Railway and Vercel often block port 53, so we prioritize port 443.
    """
    targets = [
        ("8.8.8.8", 443),      # Google
        ("google.com", 443),   # Web port
        ("1.1.1.1", 443)       # Cloudflare
    ]

    for host, port in targets:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except (socket.timeout, socket.error):
            continue
        except Exception as e:
            logger.debug(f"Connectivity check failed for {host}:{port} - {str(e)}")
            continue
    return False

def clean_name(name):
    """Helper to clean extracted names from common prepositions."""
    name = name.strip()
    name = re.sub(r'^(?:for|to|of|bought|bought\s+by)\s+', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+(?:for|to|of)$', '', name, flags=re.IGNORECASE)
    return name.strip()

def parse_smart_input(text):
    """
    Hybrid Parser using Gemini for complex multi-item invoice parsing.
    """
    text = text.strip()
    if not text:
        return None

    api_key = getattr(settings, 'GEMINI_API_KEY', None)
    online = is_online()

    if not api_key:
        logger.warning("GEMINI_API_KEY not found in settings.")
    if not online:
        logger.warning("is_online() returned False, skipping Gemini parsing.")

    # 1. Try Online AI Parsing if connected
    if api_key and online:
        try:
            client = genai.Client(api_key=api_key)
            model_id = "gemini-2.5-flash"

            prompt = (
                "You are an expert financial parsing assistant for Nigerian MSMEs. Identify the intent and extract structured data.\n"
                "Intents: 'invoice' (recording a sale) or 'query' (asking a business question).\n\n"
                "For 'invoice', extract:\n"
                "- customer_name (default: 'Walk-in Customer')\n"
                "- customer_phone (if any)\n"
                "- amount_paid (deposit or total paid)\n"
                "- items: list of {product_name, quantity, unit_price, total_price}\n"
                "- subtotal (sum of all item totals)\n\n"
                f"Input text: \"{text}\"\n\n"
                "Return ONLY a raw JSON object."
            )
            
            response = client.models.generate_content(
                model=model_id,
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            
            data = json.loads(response.text)
            intent = data.get('intent', 'invoice')
            
            if intent == 'query':
                return {
                    'intent': 'query',
                    'query_type': data.get('query_type', 'general'),
                    'text': data.get('text', text)
                }

            # Normalize items list
            items = data.get('items', [])
            if not items and data.get('product_name'):
                items = [{
                    'product_name': data.get('product_name'),
                    'quantity': data.get('quantity', 1),
                    'total_price': data.get('amount', 0),
                    'unit_price': data.get('amount', 0) / (data.get('quantity') or 1) if data.get('amount') else 0
                }]

            # COMPATIBILITY LAYER: Safely extract a single product_name for core/views.py line 120
            first_product = "General Goods"
            if items and len(items) > 0:
                first_product = items[0].get('product_name', 'General Goods')
            elif data.get('product_name'):
                first_product = data.get('product_name')

            return {
                'intent': 'invoice',
                'product_name': first_product,  # <--- THIS STOPS THE KEYERROR
                'customer_name': data.get('customer_name', 'Walk-in Customer') or 'Walk-in Customer',
                'customer_phone': data.get('customer_phone', ''),
                'amount_paid': Decimal(str(data.get('amount_paid', 0))),
                'subtotal': Decimal(str(data.get('subtotal', data.get('amount', 0)))),
                'items': items
            }
        except Exception as e:
            logger.error(f"AI Parsing Error: {str(e)}")
            pass

    # 2. Offline Token-based Heuristic Fallback
    return _parse_smart_input_offline(text)

def _parse_smart_input_offline(text):
    text_lower = text.lower()

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

    phone = ''
    phone_match = re.search(r'\b(?:\+?234|0)\d{9,11}\b', text)
    if phone_match:
        phone = phone_match.group(0)
        text = text.replace(phone, ' ').strip()

    amount_paid = Decimal('0.00')
    paid_match = re.search(r'\b(?:paid|paying|deposit|advance|payment)(?:\s+of)?\s*(?:₦|n|N)?\s*(\d+(?:[.,]\d+)?\s*[kK]?)\b', text, re.IGNORECASE)
    if paid_match:
        amount_paid = parse_numeric_val(paid_match.group(1))
        text = text[:paid_match.start()] + " " + text[paid_match.end():]
        text = re.sub(r'\s+', ' ', text).strip()

    amount = Decimal('0.00')
    amount_match = re.search(r'\b(?:for|at|costing|price|total|value|worth)(?:\s+of)?\s*(?:₦|n|N)?\s*(\d+(?:[.,]\d+)?\s*[kK]?)\b', text, re.IGNORECASE)
    if amount_match:
        amount = parse_numeric_val(amount_match.group(1))
        text = text[:amount_match.start()] + " " + text[amount_match.end():]
        text = re.sub(r'\s+', ' ', text).strip()
    else:
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

    quantity = 1
    qty_match = re.search(r'\b(\d+)\s*(?:bags?\s+of|bags?|pcs?|pieces?|cartons?|pkts?|packs?|items?|kg|liters?|units?)\b', text, re.IGNORECASE)
    if qty_match:
        quantity = int(qty_match.group(1))
        text = text[:qty_match.start()] + " " + text[qty_match.end():]
        text = re.sub(r'\s+', ' ', text).strip()
    else:
        lead_qty_match = re.match(r'^(\d+)\s+([a-zA-Z].*)$', text)
        if lead_qty_match:
            quantity = int(lead_qty_match.group(1))
            text = lead_qty_match.group(2).strip()

    customer_name = "Walk-in Customer"
    product_name = ""

    verb_match = re.search(r'\b(bought|purchased|took|ordered|wants|got|buys|purchases|takes)\b', text, re.IGNORECASE)
    if verb_match:
        cust_part = text[:verb_match.start()].strip()
        prod_part = text[verb_match.end():].strip()
        if cust_part:
            customer_name = cust_part
        if prod_part:
            product_name = prod_part
    else:
        split_match = re.search(r'\b(to|for)\b', text, re.IGNORECASE)
        if split_match:
            prod_part = text[:split_match.start()].strip()
            cust_part = text[split_match.end():].strip()
            if prod_part:
                product_name = prod_part
            if cust_part:
                customer_name = cust_part
        else:
            words = text.split()
            if len(words) >= 2:
                product_name = words[0]
                customer_name = " ".join(words[1:])
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
    Hybrid Business Setup Parser using Gemini for smart onboarding.
    """
    text = text.strip()
    if not text:
        return None

    api_key = getattr(settings, 'GEMINI_API_KEY', None)
    online = is_online()

    if api_key and online:
        try:
            client = genai.Client(api_key=api_key)
            prompt = (
                "You are an expert business consultant. Extract structured data from this informal business description:\n"
                f"\"{text}\"\n\n"
                "Return ONLY a raw JSON object with these keys:\n"
                "- business_name\n"
                "- industry (one of: 'retail', 'services', 'manufacturing', 'other')\n"
                "- phone_number\n"
                "- address\n"
                "- tin (Tax ID, if mentioned)\n"
                "- contact_email\n"
                "- primary_products (a string with comma-separated products or services)\n"
            )
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            data = json.loads(response.text)
            return {
                'business_name': data.get('business_name', 'My Business') or 'My Business',
                'industry': data.get('industry', 'other') or 'other',
                'phone_number': data.get('phone_number', '') or '',
                'address': data.get('address', '') or '',
                'tin': data.get('tin', '') or '',
                'contact_email': data.get('contact_email', '') or '',
                'primary_products': data.get('primary_products', '') or '',
            }
        except Exception as e:
            logger.error(f"Business Setup Parsing Error: {str(e)}")
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
    api_key = getattr(settings, 'GEMINI_API_KEY', None)
    if not api_key:
        return "Connect your Gemini API Key in settings to unlock personalized AI business insights."

    if not is_online():
        return "YB AI is currently offline. Please check your internet connection for new insights."

    try:
        client = genai.Client(api_key=api_key)
        prompt = (
            f"As a business consultant for Nigerian MSMEs, analyze: Sales N{sales_data}, Debt N{debt_data}. "
            "Give 3 concise actionable tips. Max 60 words."
        )
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini AI Error: {str(e)}")
        if "401" in str(e) or "API_KEY_INVALID" in str(e):
            return "Your Gemini API Key appears to be invalid. Please check your configuration."
        return "YB AI is experiencing high traffic. Please check back in a moment for your insights."
