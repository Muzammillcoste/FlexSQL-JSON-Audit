import pandas as pd
import ast

def processing(dfs):
    merchants = dfs[0]
    payment_events = dfs[1]

    # 1. Identify EMEA merchant_ids
    # Using case-insensitive match for region, although 'EMEA' is specified exactly
    emea_merchant_ids = merchants[merchants['region'] == 'EMEA']['merchant_id'].tolist()

    # 2. Process payloads and calculate amount in USD
    def parse_and_get_usd_amount(row):
        try:
            # Parse the Python-style dictionary string
            p = ast.literal_eval(row['payload'])
            
            # Extract relevant fields. Based on the example, status is 'state'
            # and currency is 'currency_code'. Using get() for safety.
            status = str(p.get('state', '')).lower()
            currency = str(p.get('currency_code', '')).lower()
            amount_cents = float(p.get('amount_cents', 0))
            
            # Filter for succeeded USD payments
            if status == 'succeeded' and currency == 'usd':
                return amount_cents / 100.0
            else:
                return 0.0
        except (ValueError, SyntaxError, TypeError):
            # If payload cannot be parsed or relevant fields are missing, ignore
            return 0.0

    # Apply the parsing function
    payment_events['amount_usd'] = payment_events.apply(parse_and_get_usd_amount, axis=1)
    
    # 3. Filter for EMEA merchants
    emea_payments = payment_events[payment_events['merchant_id'].isin(emea_merchant_ids)]
    
    # 4. Sum the amount and round to 2 decimal places
    total_amount = round(emea_payments['amount_usd'].sum(), 2)
    
    return pd.DataFrame({'total_amount': [total_amount]})