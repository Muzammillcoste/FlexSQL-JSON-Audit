import pandas as pd
import json
import ast

def processing(dfs):
    # Use the first provided DataFrame
    df = dfs[0].copy()

    # Convert 'created_at' to datetime and filter for Q2 2025 (April, May, June)
    df['created_at'] = pd.to_datetime(df['created_at'])
    df = df[(df['created_at'] >= '2025-04-01') & (df['created_at'] < '2025-07-01')]

    # Function to extract status, currency, and normalize amount from the payload
    def extract_fields(row):
        payload = {}
        # Parse payload: handle potential string representation or direct dict
        if isinstance(row, str):
            try:
                # Attempt literal_eval first, handling Python dictionary syntax (often used in SQL payloads)
                payload = ast.literal_eval(row)
            except (ValueError, SyntaxError):
                try:
                    # Fallback to standard JSON loads
                    payload = json.loads(row)
                except (ValueError, json.JSONDecodeError):
                    return pd.Series([None, None, 0.0], index=['status', 'currency', 'amount'])
        elif isinstance(row, dict):
            payload = row
        else:
            return pd.Series([None, None, 0.0], index=['status', 'currency', 'amount'])
        
        # Extract status (checking both 'state' and 'status')
        status = payload.get('state') or payload.get('status')
        # Extract currency (checking both 'currency_code' and 'currency')
        currency = payload.get('currency_code') or payload.get('currency')
        
        # Normalize amount
        amount = 0.0
        if 'amount_cents' in payload and payload['amount_cents'] is not None:
            # If amount_cents is present, convert to EUR
            try:
                amount = float(payload['amount_cents']) / 100.0
            except (ValueError, TypeError):
                amount = 0.0
        elif 'amount' in payload and payload['amount'] is not None:
            # If amount is present directly, use it as is
            try:
                amount = float(payload['amount'])
            except (ValueError, TypeError):
                amount = 0.0
        
        # Return lower-case status/currency for case-insensitive filtering
        return pd.Series([str(status).lower() if status else None,
                          str(currency).lower() if currency else None,
                          amount], index=['status', 'currency', 'amount'])

    if not df.empty:
        # Extract fields and concatenate to the main DataFrame
        extracted = df['payload'].apply(extract_fields)
        df = pd.concat([df, extracted], axis=1)

        # Filter for "succeeded" EUR payments
        filtered_df = df[(df['status'] == 'succeeded') & (df['currency'] == 'eur')]
        
        # Sum the total amount and round to 2 decimal places
        total_amount = round(filtered_df['amount'].sum(), 2)
    else:
        total_amount = 0.00
        
    return pd.DataFrame({'total_amount_eur': [total_amount]})