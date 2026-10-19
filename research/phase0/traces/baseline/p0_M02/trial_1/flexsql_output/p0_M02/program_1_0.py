import pandas as pd
import json

def processing(dfs):
    """
    Calculates the total number of units (sum of item quantities) of products 
    in the 'electronics' category across all orders with status 'delivered'.
    """
    # Load the orders DataFrame
    orders = dfs[0]
    
    # 1. Filter rows where the status is 'delivered'
    delivered_orders = orders[orders['status'] == 'delivered'].copy()
    
    # 2. Parse the details column and collect all items
    all_items = []
    
    for details_str in delivered_orders['details']:
        try:
            # Parse the JSON string
            details = json.loads(details_str)
            # Extract the 'items' list
            items = details.get('items', [])
            all_items.extend(items)
        except (json.JSONDecodeError, TypeError):
            # Skip invalid JSON or cases where 'items' cannot be extracted
            continue
            
    # Convert list of items to a DataFrame
    if not all_items:
        return pd.DataFrame({'total_units': [0]})
        
    items_df = pd.DataFrame(all_items)
    
    # 3. Filter for items where the category is 'electronics'
    # Ensure category exists and match 'electronics'
    if 'category' in items_df.columns:
        electronics_df = items_df[items_df['category'] == 'electronics']
    else:
        return pd.DataFrame({'total_units': [0]})
    
    # 4. Sum the 'qty' values to get the total number of units
    if 'qty' in electronics_df.columns:
        total_units = electronics_df['qty'].sum()
    else:
        total_units = 0
    
    return pd.DataFrame({'total_units': [total_units]})