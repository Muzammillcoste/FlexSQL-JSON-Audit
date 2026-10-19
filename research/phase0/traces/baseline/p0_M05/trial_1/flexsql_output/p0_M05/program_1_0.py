import pandas as pd
import json

def processing(dfs):
    """
    Counts the number of orders with status 'delivered' shipped to the city of Lyon.
    """
    df = dfs[0]
    
    # Filter by status 'delivered'
    df_delivered = df[df['status'] == 'delivered'].copy()
    
    # Helper to parse the JSON details and safely extract the city
    def get_city(details_str):
        try:
            # Although the prompt mentioned a specific string pattern, 
            # parsing the JSON is more robust for data extraction.
            details = json.loads(details_str)
            # Safely navigate the nested dictionary structure
            return details.get('shipping', {}).get('address', {}).get('city')
        except (json.JSONDecodeError, AttributeError, TypeError):
            # If JSON is invalid or structure is missing
            return None
    
    # Extract city for each delivered order
    df_delivered['city'] = df_delivered['details'].apply(get_city)
    
    # Filter for orders in 'Lyon' and count them
    # Use explicit string comparison for the city
    lyon_orders_count = (df_delivered['city'] == 'Lyon').sum()
    
    # Return count as a DataFrame
    return pd.DataFrame({'order_count': [lyon_orders_count]})