import pandas as pd
import json

def processing(dfs):
    merchants = dfs[0]
    payment_events = dfs[1]

    # Join the merchants and payment_events tables on merchant_id
    merged = pd.merge(merchants, payment_events, on='merchant_id')

    # Filter for the 'EMEA' region
    emea_payments = merged[merged['region'] == 'EMEA'].copy()

    def get_amount(payload_str):
        try:
            p = json.loads(payload_str)
            obj = p.get('object')
            
            # Normalize fields based on payload structure
            if obj == 'payment_intent':
                state = str(p.get('state', '')).lower()
                currency = str(p.get('currency_code', '')).lower()
                # Check for successful, USD payments
                if state == 'succeeded' and currency == 'usd':
                    # Amount is in cents, convert to dollars
                    return float(p.get('amount_cents', 0)) / 100.0
            
            elif obj == 'charge':
                status = str(p.get('status', '')).lower()
                currency = str(p.get('currency', '')).lower()
                # Check for successful, USD payments
                if status == 'succeeded' and currency == 'usd':
                    # Amount is already in dollars
                    return float(p.get('amount', 0))
            
            return 0.0
        except (json.JSONDecodeError, TypeError, ValueError):
            return 0.0

    # Calculate individual USD amounts
    emea_payments['usd_amount'] = emea_payments['payload'].apply(get_amount)

    # Sum all amounts
    total_amount = emea_payments['usd_amount'].sum()
    
    # Return result rounded to 2 decimal places
    return pd.DataFrame({'total_amount_usd': [round(total_amount, 2)]})