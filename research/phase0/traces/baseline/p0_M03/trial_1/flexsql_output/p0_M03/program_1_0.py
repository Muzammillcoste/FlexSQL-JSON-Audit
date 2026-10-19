import pandas as pd
import json

def processing(dfs):
    """
    Processes the orders dataframe to calculate the average shipping cost 
    for 'express' orders by parsing the nested JSON 'details' column.
    """
    orders = dfs[0].copy()
    
    # Helper to parse each JSON string safely
    def parse_json(s):
        try:
            return json.loads(s)
        except (TypeError, json.JSONDecodeError):
            return {}
            
    # Apply the parsing
    orders['details_parsed'] = orders['details'].apply(parse_json)
    
    # Extract shipping method and cost
    # We safely check for the 'shipping' key and its sub-keys
    shipping_list = [d.get('shipping') if isinstance(d, dict) else None for d in orders['details_parsed']]
    
    orders['shipping_method'] = [s.get('method') if isinstance(s, dict) else None for s in shipping_list]
    orders['shipping_cost'] = [s.get('cost') if isinstance(s, dict) else None for s in shipping_list]
    
    # Ensure shipping costs are numeric (handles potential mixed/string types)
    orders['shipping_cost'] = pd.to_numeric(orders['shipping_cost'], errors='coerce')                
    
    # Filter for 'express' shipping method
    express_orders = orders[orders['shipping_method'] == 'express']
    
    # Calculate average cost for express orders
    avg_cost = express_orders['shipping_cost'].mean()
    
    # Return the result as a DataFrame, rounded to two decimal places
    # If there are no express orders, avg_cost might be NaN, handling that might be necessary
    result_val = round(float(avg_cost), 2) if not pd.isna(avg_cost) else 0.0
    
    return pd.DataFrame({'average_shipping_cost': [result_val]})