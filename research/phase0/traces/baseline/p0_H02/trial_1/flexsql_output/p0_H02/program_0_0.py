import pandas as pd
import ast

def processing(dfs):
    df = dfs[0]
    # In case the table is empty
    if df.empty:
        return pd.DataFrame({'succeeded_visa_payments': [0]})
    
    count = 0
    for p_str in df['payload']:
        # Replace common JSON-like values to make it valid for ast.literal_eval
        # The payload strings use single quotes and Python-like 'null', 'true', 'false'
        clean_str = p_str.replace('null', 'None').replace('true', 'True').replace('false', 'False')
        try:
            payload = ast.literal_eval(clean_str)
        except:
            # Skip rows where the JSON parsing fails
            continue

        # Need to identify succeeded payments and Visa cards
        is_succeeded = False
        is_visa = False
        
        # Check for 'charge' or 'payment_intent'
        obj_type = payload.get('object')
        
        if obj_type == 'payment_intent':
            # Check status (e.g., 'SUCCEEDED' or 'succeeded')
            if str(payload.get('state', '')).lower() == 'succeeded':
                is_succeeded = True
            
            # Check network
            # payment_method: {'type': 'card', 'card': {'network': 'VISA', 'last4': 2323}}
            pm = payload.get('payment_method')
            if pm and isinstance(pm, dict):
                if pm.get('type') == 'card':
                    card_info = pm.get('card', {})
                    if str(card_info.get('network', '')).lower() == 'visa':
                        is_visa = True
                        
        elif obj_type == 'charge':
            # Check status
            if str(payload.get('status', '')).lower() == 'succeeded':
                is_succeeded = True
                
            # Check brand
            # card: {'brand': 'visa', 'last4': '0964'}
            card_info = payload.get('card')
            if card_info and isinstance(card_info, dict):
                if str(card_info.get('brand', '')).lower() == 'visa':
                    is_visa = True
                    
        # Both conditions must be met
        if is_succeeded and is_visa:
            count += 1
            
    return pd.DataFrame({'succeeded_visa_payments': [count]})