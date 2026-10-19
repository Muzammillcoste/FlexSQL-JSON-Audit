import pandas as pd
import json

def processing(dfs):
    carriers_df = dfs[0]
    shipments_df = dfs[1]

    # 1. Find carrier_code for 'FastFreight'
    target_carrier = carriers_df[carriers_df['carrier_name'] == 'FastFreight']
    
    if target_carrier.empty:
        return pd.DataFrame({'total_units': [0]})
        
    carrier_code = target_carrier['carrier_code'].iloc[0]

    # 2. Filter shipments by the carrier_code
    shipments_filtered = shipments_df[shipments_df['carrier_code'] == carrier_code]

    # 3. Recursive function to sum 'qty' in any nested structure within the manifest
    def get_total_qty(data):
        if isinstance(data, dict):
            total = 0
            # If this dictionary represents an 'item' (or contains 'qty'), add its quantity
            if 'qty' in data:
                total += data['qty']
            # Continue looking for nested structures('items', 'packages', 'boxes', etc.)
            for key in data:
                if key != 'qty':
                    total += get_total_qty(data[key])
            return total
        elif isinstance(data, list):
            total = 0
            # Traverse each element in the list
            for item in data:
                total += get_total_qty(item)
            return total
        else:
            # If data is not a dict or a list (e.g., int, float, str), return 0
            return 0
    
    # 4. Define a wrapper function to parse the JSON string and calculate the total qty
    def parse_and_sum(manifest_str):
        try:
            # Parse the string into a dict object
            manifest_dict = json.loads(manifest_str)
            return get_total_qty(manifest_dict)
        except (ValueError, TypeError, json.JSONDecodeError):
            # If parsing fails or manifest is not in valid format, treat as 0
            return 0
            
    # Apply calculation for each manifest string and sum the results
    total_units = shipments_filtered['manifest'].apply(parse_and_sum).sum()
    
    return pd.DataFrame({'total_units': [int(total_units)]})