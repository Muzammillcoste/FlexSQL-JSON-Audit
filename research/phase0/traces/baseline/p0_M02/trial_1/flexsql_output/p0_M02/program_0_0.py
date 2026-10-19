import pandas as pd
import json

def processing(dfs):
    # The 'orders' table is the first DataFrame
    orders_df = dfs[0]
    
    # Filter for 'delivered' status
    delivered_orders = orders_df[orders_df['status'] == 'delivered']
    
    total_electronics_qty = 0
    
    # Iterate through each row to process the 'details' JSON string
    for details_str in delivered_orders['details']:
        # Parse the JSON string
        try:
            # Handle potential scenarios: if it's a string, load it as JSON; 
            # if it's already a dictionary, use it as is.
            if isinstance(details_str, str):
                details = json.loads(details_str)
            else:
                details = details_str
            
            # Access the 'items' list
            items = details.get('items', [])
            
            # Ensure items is a list before iterating
            if isinstance(items, list):
                # Extract and sum quantities for 'electronics'
                for item in items:
                    # Defensive check: ensure item is a dict and has 'category'
                    if isinstance(item, dict) and item.get('category') == 'electronics':
                        total_electronics_qty += item.get('qty', 0)
        except (json.JSONDecodeError, TypeError):
            # Skip if invalid JSON or unexpected type
            continue
                
    # Return the result as a Pandas DataFrame
    return pd.DataFrame({'total_electronics_qty': [total_electronics_qty]})