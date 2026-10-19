import ast
import pandas as pd
import numpy as np
import json

def processing(dfs):
    # A robust function to parse both JSON and Python-style dictionary strings
    def parse_payload(s):
        try:
            # Try parsing as JSON first
            return json.loads(s)
        except:
            # If JSON fails, it might be due to single quotes or other Pythonic syntax.
            # Replace JSON's 'null', 'true', 'false' with Python's 'None', 'True', 'False'
            # to make it compatible with ast.literal_eval.
            s = s.replace('null', 'None').replace('true', 'True').replace('false', 'False')
            return ast.literal_eval(s)
            
    # Load and parse the payload column
    payloads = [parse_payload(x) for x in dfs[0]['payload']]
    df = pd.DataFrame(payloads)
    
    # 1. Normalize currency: prioritize 'currency_code', then 'currency'
    currency = pd.Series([None] * len(df))
    if 'currency_code' in df.columns:
        currency = currency.combine_first(df['currency_code'])
    if 'currency' in df.columns:
        currency = currency.combine_first(df['currency'])
        
    # 2. Normalize status: prioritize 'state', then 'status'
    status = pd.Series([None] * len(df))
    if 'state' in df.columns:
        status = status.combine_first(df['state'])
    if 'status' in df.columns:
        status = status.combine_first(df['status'])
        
    # 3. Normalize amount: 'amount_cents' (divide by 100) or 'amount'
    normalized_amount = pd.Series([np.nan] * len(df))
    
    # Prioritize amount_cents if it exists
    if 'amount_cents' in df.columns:
        # Convert to float to handle potential integer/string parsing
        cents_amount = df['amount_cents'].astype(float) / 100.0
        normalized_amount = normalized_amount.combine_first(cents_amount)
        
    # Fill in from the 'amount' field if it exists
    if 'amount' in df.columns:
        normalized_amount = normalized_amount.combine_first(df['amount'].astype(float))
        
    # 4. Create structured DataFrame for filtering
    normalized_df = pd.DataFrame({
        'currency': currency.fillna('').astype(str).str.lower(),
        'status': status.fillna('').astype(str).str.lower(),
        'amount': normalized_amount
    })
    
    # 5. Filter for 'succeeded' and 'usd' (case-insensitive)
    filtered_df = normalized_df[
        (normalized_df['currency'] == 'usd') & 
        (normalized_df['status'] == 'succeeded')
    ]
    
    # 6. Find the maximum amount
    max_amount = filtered_df['amount'].max()
    
    # 7. Return the result as a DataFrame
    return pd.DataFrame({'max_amount': [max_amount]})