import pandas as pd
import json
import ast

def processing(dfs):
    # Helper to parse both JSON and dictionary formatted strings
    def parse_payload(payload_str):
        try:
            return json.loads(payload_str)
        except:                
            try:
                return ast.literal_eval(payload_str)
            except:
                return {}

    df = dfs[0]
    count = 0
    
    for payload_str in df['payload']:
        if not isinstance(payload_str, str):
            continue
            
        data = parse_payload(payload_str)
        if not isinstance(data, dict):
            continue
            
        obj = data.get('object', '')
        
        status = None
        brand = None
        
        # Extract status and brand based on object type
        if obj == 'charge':
            status = data.get('status')
            brand = (data.get('card') or {}).get('brand')
        elif obj == 'payment_intent':
            status = data.get('state')
            card_info = (data.get('payment_method') or {}).get('card') or {}
            brand = card_info.get('network')
        
        # Fallback for wallet transactions or other structures
        if not status:
            trans = (data.get('transaction') or {}).get('result') or {}
            status = trans.get('status')
        if not brand:
            inst = (data.get('instrument') or {}).get('details') or {}
            brand = inst.get('card_brand')
        
        # Verify status and brand and check for a succeeded visa payment (case-insensitive)
        if isinstance(status, str) and isinstance(brand, str):
            if status.lower() == 'succeeded' and brand.lower() == 'visa':
                count += 1
                
    return pd.DataFrame({'succeeded_visa_payments_count': [count]})