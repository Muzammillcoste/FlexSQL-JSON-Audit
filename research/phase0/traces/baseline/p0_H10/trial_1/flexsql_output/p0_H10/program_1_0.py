import pandas as pd
import ast
import json

def processing(dfs):
    df = dfs[0]
    
    # Combined parsing function to be robust
    def parse_row(payload_str):
        # 1st try: Attempt json.loads
        try:
            return json.loads(payload_str)
        except (json.JSONDecodeError, TypeError):
            # 2nd try: Attempt literal_eval with common JSON to Python literal replacements
            try:
                # Replace JSON-specific literals with Python-specific literals
                s = payload_str.replace('null', 'None').replace('true', 'True').replace('false', 'False')
                return ast.literal_eval(s)
            except:
                return {}
                
    # Parse the payload column
    data = [parse_row(p) for p in df['payload']]
    df_parsed = pd.DataFrame(data)

    # Normalize fields to allow consistent filtering
    def get_amount(row):
        # 'payment_intent' uses 'amount_cents' / 100, 'charge' may use 'amount'
        if row.get('amount_cents') is not None:
            return float(row['amount_cents']) / 100.0
        elif row.get('amount') is not None:
            return float(row['amount'])
        return None

    def get_currency(row):
        val = row.get('currency_code') or row.get('currency')
        return str(val).lower() if val is not None else None

    def get_status(row):
        val = row.get('state') or row.get('status')
        return str(val).lower() if val is not None else None

    df_parsed['normalized_amount'] = df_parsed.apply(get_amount, axis=1)
    df_parsed['normalized_currency'] = df_parsed.apply(get_currency, axis=1)
    df_parsed['normalized_status'] = df_parsed.apply(get_status, axis=1)

    # Filter for succeeded USD payments (case-insensitive)
    mask = (df_parsed['normalized_status'] == 'succeeded') & \
           (df_parsed['normalized_currency'] == 'usd')

    # Calculate the maximum succeeded USD amount
    if df_parsed[mask].empty:
        max_amount = 0.0
    else:
        max_amount = df_parsed[mask]['normalized_amount'].max()

    # Return the result as a DataFrame
    return pd.DataFrame({'max_succeeded_usd_amount': [max_amount]})