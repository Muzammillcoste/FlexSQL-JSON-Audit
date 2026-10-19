import pandas as pd
import json

def processing(dfs):
    # Copy to avoid modifying the original dataframe
    df = dfs[0].copy()
    
    # Ensure created_at is converted to datetime for filtering
    df['created_at'] = pd.to_datetime(df['created_at'])
    
    # Filter by date first to reduce processing - Q2 2025: April 1 to June 30
    # Included 2025-04-01 00:00:00 to 2025-06-30 23:59:59
    df = df[(df['created_at'] >= '2025-04-01') & (df['created_at'] < '2025-07-01')].copy()
    
    def parse_payload(payload_str):
        try:
            # Handle potential JSON parsing errors
            data = json.loads(payload_str)
            
            # The schema depends on the 'object' field
            obj_type = data.get('object')
            
            amount = 0.0
            currency = ''
            status = ''
            
            # Handle different recognized payload structures
            if obj_type == 'payment_intent':
                # payment_intent uses 'amount_cents', 'currency_code', 'state'
                # Convert cents to base units (e.g., EUR)
                amount = float(data.get('amount_cents', 0)) / 100.0
                currency = str(data.get('currency_code', '')).lower()
                status = str(data.get('state', '')).lower()
            elif obj_type == 'charge':
                # charge uses 'amount', 'currency', 'status'
                amount = float(data.get('amount', 0))
                currency = str(data.get('currency', '')).lower()
                status = str(data.get('status', '')).lower()
            elif 'transaction' in data:
                # Some payloads have a nested 'transaction' key
                transaction = data.get('transaction', {})
                if not isinstance(transaction, dict):
                    transaction = {}
                amount = float(transaction.get('amount', 0))
                currency = str(transaction.get('currency', '')).lower()
                status = str(transaction.get('status', '')).lower()
            else:
                # If we cannot identify the structure, skip it
                return None
            
            return {'amount': amount, 'currency': currency, 'status': status}
        except (json.JSONDecodeError, ValueError, TypeError):
            # If JSON parsing or field extraction fails, skip it
            return None
            
    # Apply parsing to each row in the dataframe
    parsed_data = df['payload'].apply(parse_payload)
    
    # Create the DataFrame from parsed results, ignoring None values
    parsed_list = [x for x in parsed_data if x is not None]
    
    if not parsed_list:
        # Return a DataFrame with 0.0 if no valid results found
        return pd.DataFrame({'total_amount_euros': [0.0]})
        
    parsed_df = pd.DataFrame(parsed_list)
    
    # Filter for succeeded payments in EUR (both are case-insensitive as per requirements)
    results = parsed_df[(parsed_df['status'] == 'succeeded') & (parsed_df['currency'] == 'eur')]
    
    # Sum the amounts
    total_amount_euros = results['amount'].sum()
    
    # Return as a DataFrame, rounded to 2 decimal places
    return pd.DataFrame({'total_amount_euros': [round(total_amount_euros, 2)]})