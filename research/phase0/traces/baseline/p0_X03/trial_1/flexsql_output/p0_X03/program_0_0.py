import pandas as pd
import ast

def processing(dfs):
    # The 'shipments' table is in dfs[0]
    df = dfs[0].copy()
    
    # 1. Ensure 'created_at' is datetime and filter for June 2025
    df['created_at'] = pd.to_datetime(df['created_at'])
    june_start = '2025-06-01'
    july_start = '2025-07-01'
    
    june_shipments = df[(df['created_at'] >= june_start) & (df['created_at'] < july_start)].copy()
    
    # 2. Define a function to check for the 'DELIVERED' status in the tracking history.
    # The 'tracking' column is a string representation of a dictionary,
    # often with single quotes, making it incompatible with json.loads().
    # ast.literal_eval() is a safer alternative to evaluate this string representation.
    def is_delivered(tracking_str):
        if not isinstance(tracking_str, str):
            return False
            
        try:
            # Safely evaluate the string representation of the dictionary
            data = ast.literal_eval(tracking_str)
            events = data.get('events', [])
            
            # The 'events' key should be a list
            if isinstance(events, list):
                # Check if any event has the code 'DELIVERED'
                return any(isinstance(event, dict) and event.get('code') == 'DELIVERED' for event in events)
            return False
        except (ValueError, SyntaxError, AttributeError):
            # Handle potential parsing or unexpected data structure errors gracefully
            return False

    # Apply the check and count the delivered shipments
    june_shipments['is_delivered'] = june_shipments['tracking'].apply(is_delivered)
    result_count = int(june_shipments['is_delivered'].sum())
    
    # Return as a DataFrame containing the final count
    return pd.DataFrame({'delivered_shipment_count': [result_count]})