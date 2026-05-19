import os
import re
from decimal import Decimal

def parse_smart_input(text):
    """
    Parses dynamic shorthand and natural language text inputs into structured data dictionaries.
    Supports extract of:
    - Customer Name (e.g. Moses, Musa, Walk-in Customer)
    - Product Name (e.g. garri, Rice, Bread)
    - Subtotal/Amount (e.g. 20000, 5k)
    - Amount Paid (e.g. paid 15000, paid 15k)
    - Quantity (e.g. 5 bags of, 5, 10 kg)
    """
    text = text.strip()
    if not text:
        return None

    # Check for Gemini API key and use Generative AI if present
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        try:
            import google.generativeai as genai
            import json
            
            genai.configure(api_key=api_key)
            model_name = "gemini-2.5-flash"
            try:
                model = genai.GenerativeModel(model_name)
            except:
                model_name = "gemini-1.5-flash"
                model = genai.GenerativeModel(model_name)
                
            prompt = (
                "You are an expert financial parsing assistant for Nigerian MSMEs. Your task is to identify the intent of the user's input and extract structured data.\n\n"
                "Intents:\n"
                "1. \"invoice\": User is recording a sale/transaction.\n"
                "2. \"query\": User is asking a question about their business (e.g., 'Who owes me?', 'How much did I sell today?').\n\n"
                "Examples:\n"
                "1. \"beans for pp 5000\" -> {\"intent\": \"invoice\", \"product_name\": \"beans\", \"customer_name\": \"pp\", \"amount\": 5000, \"amount_paid\": 0, \"quantity\": 1}\n"
                "2. \"Moses bought 5 bags of garri for 20000 paid 15000\" -> {\"intent\": \"invoice\", \"product_name\": \"garri\", \"customer_name\": \"Moses\", \"amount\": 20000, \"amount_paid\": 15000, \"quantity\": 5}\n"
                "3. \"How much is my total sales?\" -> {\"intent\": \"query\", \"query_type\": \"sales_total\", \"text\": \"How much is my total sales?\"}\n"
                "4. \"Who owes me the most?\" -> {\"intent\": \"query\", \"query_type\": \"debt_top\", \"text\": \"Who owes me the most?\"}\n\n"
                "Rules for 'invoice':\n"
                "- product_name: The name of the product sold. Concise. E.g. \"beans\".\n"
                "- amount: Total price. \"5k\" -> 5000.\n"
                "- customer_name: Default to \"Walk-in Customer\".\n"
                "- amount_paid: Deposit/payment.\n"
                "- quantity: Default to 1.\n\n"
                f"Input text: \"{text}\"\n\n"
                "Return ONLY a raw JSON object, no markdown."
            )
            
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            
            resp_text = response.text.strip()
            if resp_text.startswith("```"):
                resp_text = re.sub(r'^```(?:json)?\n', '', resp_text)
                resp_text = re.sub(r'\n```$', '', resp_text).strip()
                
            data = json.loads(resp_text)
            intent = data.get('intent', 'invoice')
            
            if intent == 'query':
                return {
                    'intent': 'query',
                    'query_type': data.get('query_type'),
                    'text': data.get('text', text)
                }

            prod_name = data.get('product_name', 'General Goods') or 'General Goods'
            parsed_amount = Decimal(str(data.get('amount', 0)))
            cust_name = data.get('customer_name', 'Walk-in Customer') or 'Walk-in Customer'
            parsed_paid = Decimal(str(data.get('amount_paid', 0)))
            qty = int(data.get('quantity', 1))
            
            if parsed_amount == Decimal('0.00') and parsed_paid > Decimal('0.00'):
                parsed_amount = parsed_paid
                
            if parsed_amount > Decimal('0.00'):
                return {
                    'intent': 'invoice',
                    'product_name': prod_name,
                    'amount': parsed_amount,
                    'customer_name': cust_name,
                    'amount_paid': parsed_paid,
                    'quantity': qty
                }
        except Exception as e:
            # Fall back to heuristic parsing on any error
            pass

    # Heuristic fallback for basic queries
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

    amount_paid = Decimal('0.00')
    # 1. Extract paid amount if exists
    paid_match = re.search(r'\b(?:paid|paying|deposit|advance|payment)(?:\s+of)?\s*(?:₦|n|N)?\s*(\d+(?:[.,]\d+)?\s*[kK]?)\b', text, re.IGNORECASE)
    if paid_match:
        amount_paid = parse_numeric_val(paid_match.group(1))
        text = text[:paid_match.start()] + " " + text[paid_match.end():]
        text = re.sub(r'\s+', ' ', text).strip()

    # 2. Extract transaction amount if exists
    amount = Decimal('0.00')
    amount_match = re.search(r'\b(?:for|at|costing|price|total|value|worth)(?:\s+of)?\s*(?:₦|n|N)?\s*(\d+(?:[.,]\d+)?\s*[kK]?)\b', text, re.IGNORECASE)
    if amount_match:
        amount = parse_numeric_val(amount_match.group(1))
        text = text[:amount_match.start()] + " " + text[amount_match.end():]
        text = re.sub(r'\s+', ' ', text).strip()
    else:
        # Find any standalone number that is likely the price
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

    # 4. Determine Customer and Product Names
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

    def clean_name(name):
        name = name.strip()
        name = re.sub(r'^(?:for|to|of|bought|bought\s+by)\s+', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s+(?:for|to|of)$', '', name, flags=re.IGNORECASE)
        return name.strip()

    customer_name = clean_name(customer_name)
    product_name = clean_name(product_name)

    if not product_name:
        product_name = "General Goods"
    if not customer_name:
        customer_name = "Walk-in Customer"

    # Validation: must have a non-zero amount, and the remaining text must contain at least some description (letters)
    if amount == Decimal('0.00') or not re.search(r'[a-zA-Z]', text):
        return None

    return {
        'intent': 'invoice',
        'product_name': product_name,
        'amount': amount,
        'customer_name': customer_name,
        'amount_paid': amount_paid,
        'quantity': quantity
    }


def parse_business_setup(text):
    """
    Parses natural language business profiles into structured data fields:
    - business_name
    - industry (retail, services, manufacturing, other)
    - phone_number
    - address
    - tin
    """
    text = text.strip()
    if not text:
        return None

    # Check for Gemini API key and use Generative AI if present
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        try:
            import google.generativeai as genai
            import json
            
            genai.configure(api_key=api_key)
            model_name = "gemini-2.5-flash"
            try:
                model = genai.GenerativeModel(model_name)
            except:
                model_name = "gemini-1.5-flash"
                model = genai.GenerativeModel(model_name)
                
            prompt = (
                "You are an expert business onboarding assistant. Your job is to extract business details from the user's description.\n\n"
                f"User Description: \"{text}\"\n\n"
                "Extract the following fields and return ONLY a valid JSON object:\n"
                "- business_name: (string) The name of the business. Default to \"My Business\" if not found.\n"
                "- industry: (string) Must be one of: \"retail\", \"services\", \"manufacturing\", or \"other\". Decide based on the description.\n"
                "- phone_number: (string) The phone number of the business. Default to empty string if not found.\n"
                "- address: (string) The address of the business. Default to empty string if not found.\n"
                "- tin: (string) Tax Identification Number. Default to empty string if not found.\n\n"
                "Return ONLY a raw JSON object, no markdown, no explanation."
            )
            
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            
            resp_text = response.text.strip()
            if resp_text.startswith("```"):
                resp_text = re.sub(r'^```(?:json)?\n', '', resp_text)
                resp_text = re.sub(r'\n```$', '', resp_text).strip()
                
            data = json.loads(resp_text)
            
            return {
                'business_name': data.get('business_name', 'My Business') or 'My Business',
                'industry': data.get('industry', 'other') or 'other',
                'phone_number': data.get('phone_number', '') or '',
                'address': data.get('address', '') or '',
                'tin': data.get('tin', '') or ''
            }
        except Exception as e:
            # Fall back to heuristic parsing on any error
            pass

    # Heuristic/regex fallback:
    # 1. Extract phone number
    phone_match = re.search(r'\b(?:\+?234|0)\d{9,11}\b|\+?\d[\d\s-]{8,15}\d', text)
    phone = phone_match.group(0).strip() if phone_match else ''
    
    # 2. Extract TIN
    tin_match = re.search(r'\b\d{8}-\d{4}\b|\b\d{8,12}\b', text)
    tin = ''
    if tin_match:
        candidate = tin_match.group(0).strip()
        if candidate != phone:
            tin = candidate
        else:
            all_tins = re.findall(r'\b\d{8}-\d{4}\b|\b\d{8,12}\b', text)
            for t in all_tins:
                if t != phone:
                    tin = t
                    break
    
    # 3. Extract Industry
    industry = 'other'
    text_lower = text.lower()
    retail_kws = ['shop', 'store', 'sell', 'retail', 'boutique', 'supermarket', 'merchant', 'dealer', 'market', 'goods', 'groceries', 'clothes', 'garri', 'rice', 'bread', 'food', 'provision']
    services_kws = ['consulting', 'consultant', 'services', 'agency', 'law', 'legal', 'clinic', 'hospital', 'repair', 'salon', 'barber', 'tech', 'software', 'teaching', 'school', 'design', 'creative', 'mechanic', 'electrician']
    mfg_kws = ['factory', 'manufacturing', 'manufacturer', 'production', 'produce', 'mill', 'plant', 'assembly', 'make', 'builder', 'bakery', 'farm', 'agriculture']
    
    if any(kw in text_lower for kw in retail_kws):
        industry = 'retail'
    elif any(kw in text_lower for kw in services_kws):
        industry = 'services'
    elif any(kw in text_lower for kw in mfg_kws):
        industry = 'manufacturing'

    # 4. Extract Address
    address = ''
    address_indicators = ['street', 'st', 'road', 'rd', 'way', 'avenue', 'ave', 'lane', 'ln', 'close', 'cl', 'crescent', 'cres', 'highway', 'hwy', 'plaza', 'mall', 'complex', 'lagos', 'abuja', 'ikeja', 'yaba', 'lekki', 'nigeria', 'no.', 'plot', 'suite']
    segments = re.split(r'[,.\n]', text)
    address_parts = []
    for seg in segments:
        seg_clean = seg.strip()
        if any(indicator in seg_clean.lower() for indicator in address_indicators):
            if phone and phone in seg_clean:
                seg_clean = seg_clean.replace(phone, '').strip()
            if tin and tin in seg_clean:
                seg_clean = seg_clean.replace(tin, '').strip()
            if len(seg_clean) > 5:
                address_parts.append(seg_clean)
    if address_parts:
        address = ', '.join(address_parts)
    
    # 5. Extract Business Name
    business_name = 'My Business'
    name_patterns = [
        r'(?:name is|called|company is|business is|shop is)\s+([A-Za-z0-9\s&]+?)(?:\b(?:at|located|phone|tin|we|i)\b|$)',
        r'\b([A-Za-z0-9\s&]+?\b(?:Electronics|Enterprise|Ventures|Stores|Global|Ltd|Services|Holdings|Solutions|Hub|Bakery|Farms|Interprises))\b',
    ]
    for pattern in name_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            if len(candidate) > 2:
                business_name = candidate
                break
    
    if business_name == 'My Business':
        words = text.split()
        capitalized = [w for w in words[:5] if w[0].isupper() and w.lower() not in ['i', 'we', 'my', 'our', 'the', 'a', 'an']]
        if capitalized:
            business_name = ' '.join(capitalized)
            business_name = re.sub(r'[^\w\s]', '', business_name).strip()
        elif len(words) >= 2:
            business_name = ' '.join(words[:2])
            business_name = re.sub(r'[^\w\s]', '', business_name).strip()

    return {
        'business_name': business_name or 'My Business',
        'industry': industry,
        'phone_number': phone,
        'address': address,
        'tin': tin
    }

def get_ai_business_insights(sales_data, debt_data, inventory_data=None):
    """
    Generates personalized business insights using Gemini AI.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "Connect your Gemini API Key to unlock personalized AI business insights."

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")

        prompt = (
            "You are a professional business consultant for MSMEs in Nigeria. "
            "Analyze the following business metrics and provide 3 concise, actionable insights or advice.\n\n"
            f"Total Sales: N{sales_data}\n"
            f"Total Outstanding Debt (Gbese): N{debt_data}\n"
            f"Inventory Status: {inventory_data or 'Not tracked'}\n\n"
            "Keep advice specific to the Nigerian context. Format as a bulleted list. Max 100 words."
        )

        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception:
        return "YB AI is currently optimizing your data. Please check back in a few minutes for new insights."

