import pandas as pd
import json

def processing(dfs):
    # The DataFrame from SQL Query 1 is at dfs[0]
    df = dfs[0]
    
    # Helper to parse the 'details' JSON string
    def parse_details(row):
        try:
            # Parse the JSON string
            data = json.loads(row)
            # Access the 'shipping' sub-dictionary
            shipping = data.get('shipping', {})
            # Extract 'method' and 'cost'
            method = shipping.get('method')
            cost = shipping.get('cost')
            
            # Ensure cost is treated as a float, handling both numeric and string representations
            actual_cost = float(cost) if cost is not None else None
            return pd.Series({'method': method, 'cost': actual_cost})
        except (json.JSONDecodeError, TypeError, ValueError):
            # In case of malformed data or missing keys
            return pd.Series({'method': None, 'cost': None})
            
    # Apply parsing to create a new DataFrame with 'method' and 'cost' columns
    parsed_df = df['details'].apply(parse_details)
    
    # Filter for rows where the shipping method is exactly 'express'
    express_orders = parsed_df[parsed_df['method'] == 'express']
    
    # Calculate the mean of the shipping cost
    avg_cost = express_orders['cost'].mean()
    
    # Round the average shipping cost to 2 decimal places.
    # Handle the case where no express orders exist (mean would be NaN)
    if pd.isna(avg_cost):
        result = 0.0
    else:
        result = round(float(avg_cost), 2)
    
    # Return the result as a one-row DataFrame
    return pd.DataFrame({'average_shipping_cost': [result]})