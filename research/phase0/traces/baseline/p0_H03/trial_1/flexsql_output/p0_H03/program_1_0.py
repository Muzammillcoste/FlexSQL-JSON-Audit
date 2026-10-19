import pandas as pd
import json

def processing(dfs):
    # Load the DataFrame
    df = dfs[0].copy()
    
    # Ensure created_at is converted to datetime for time-based filtering
    df['created_at'] = pd.to_datetime(df['created_at'])
    
    # Filter for the first quarter of 2025 (January, February, March)
    # 2025-01-01 00:00:00 to 2025-03-31 23:59:59
    df = df[(df['created_at'] >= '2025-01-01') & (df['created_at'] < '2025-04-01')]
    
    total_dollars = 0.0
    
    # Process each payload
    for payload_str in df['payload']:
        try:
            data = json.loads(payload_str)
        except:
            continue
            
        obj_type = data.get('object', '').lower()
        
        # Scenario 1: Object is a 'charge'
        if obj_type == 'charge':
            status = data.get('status', '').lower()
            currency = data.get('currency', '').lower()
            
            # Check for succeeded, USD-denominated charge
            if status == 'succeeded' and currency == 'usd':
                # 'fee' is assumed to be in US dollars
                fee = data.get('fee')
                total_dollars += float(fee if fee is not None else 0.0)
                
        # Scenario 2: Object is a 'payment_intent'
        elif obj_type == 'payment_intent':
            # Check state and currency ('currency_code')
            state = data.get('state', '').lower()
            if not state:
                state = data.get('status', '').lower()
            
            currency = data.get('currency_code', '').lower()
            if not currency:
                currency = data.get('currency', '').lower()
            
            # Check for succeeded, USD-denominated payment intent
            if state == 'succeeded' and currency == 'usd':
                # Sum 'processing' fees from the 'fees' array, which are in cents
                # Exclude any other fee types (like 'fx')
                fees = data.get('fees', [])
                if isinstance(fees, list):
                    for fee_item in fees:
                        if fee_item.get('type') == 'processing':
                            cents = fee_item.get('amount_cents', 0)
                            # Convert cents to dollars
                            total_dollars += float(cents if cents is not None else 0.0) / 100.0
        
    # Prepare result dataframe rounded to 2 decimal places
    return pd.DataFrame({'total_processing_fee_usd': [round(total_dollars, 2)]})