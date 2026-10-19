import pandas as pd
import json

def processing(dfs):
    # Load the DataFrame from the first sub-query
    df = dfs[0]
    
    # 1. Parse 'created_at' and filter for the first quarter of 2025 (Jan-Mar)
    df['created_at'] = pd.to_datetime(df['created_at'])
    start_date = '2025-01-01'
    end_date = '2025-04-01'
    mask = (df['created_at'] >= start_date) & (df['created_at'] < end_date)
    df_q1 = df[mask].copy()
    
    # 2. Define a function to parse 'payload' and calculate the net fee for each row
    def calculate_net_fee(row):
        try:
            # Parse the JSON string payload
            p = json.loads(row['payload'])
            
            # Determine status and currency (handles both 'payment_intent' and 'charge' object types)
            # Use 'state' and 'currency_code' for 'payment_intent'
            # Use 'status' and 'currency' for 'charge'
            status = p.get('state') or p.get('status')
            currency = p.get('currency_code') or p.get('currency')
            
            # The currency and status must exist to be a valid payment
            if not status or not currency:
                return 0.0
            
            # Filter: status == 'succeeded' AND currency == 'USD' (case-insensitive)
            if status.lower() != 'succeeded' or currency.lower() != 'usd':
                return 0.0
            
            # Calculate net fee
            # 'payment_intent' structures fees as a list
            # 'charge' structures the fee as a single field
            obj_type = p.get('object')
            
            if obj_type == 'payment_intent':
                # Sum all fees except foreign-exchange (FX) fees
                # "calculate the net fee as the 'fee' minus 'fx_fee'"
                fees = p.get('fees')
                if fees is None:
                    fees = []
                
                # Sum fees (in cents) where type != 'fx', then convert to dollars
                total_cents = sum(f.get('amount_cents', 0) for f in fees if f.get('type') != 'fx')
                return total_cents / 100.0
            
            elif obj_type == 'charge':
                # 'fee' for 'charge' objects is already in dollars
                # Based on analysis, 'charge' objects do not contain fx_fee
                return float(p.get('fee', 0))
            
            # If object type is unknown, treat as 0
            return 0.0
        except Exception:
            # If there's any error in parsing a row, treat as 0
            return 0.0
            
    # Apply the calculation
    df_q1['net_fee'] = df_q1.apply(calculate_net_fee, axis=1)
    
    # 3. Sum all net fees and round the final total to two decimal places
    total_fee = round(df_q1['net_fee'].sum(), 2)
    
    # 4. Return result as a Pandas DataFrame
    return pd.DataFrame({'total_processing_fee': [total_fee]})