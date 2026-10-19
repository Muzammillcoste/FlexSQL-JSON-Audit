import pandas as pd
import json

def processing(dfs):
    """
    Calculates the total quantity of items shipped by 'FastFreight' by parsing
    the JSON manifest for each shipment, accounting for nested structures.
    """
    df_shipments = dfs[0]
    df_carriers = dfs[1]

    # Join the 'shipments' and 'carriers' tables on 'carrier_code'
    merged_df = df_shipments.merge(df_carriers, on='carrier_code', how='inner')
    
    # Filter for the specific carrier name
    filtered_df = merged_df[merged_df['carrier_name'] == 'FastFreight']
    
    def calculate_total_qty(manifest_str):
        try:
            manifest = json.loads(manifest_str)
        except (TypeError, json.JSONDecodeError):
            return 0
        
        total = 0
        # Ensure 'packages' exists and is a list
        if 'packages' in manifest and isinstance(manifest['packages'], list):
            for pkg in manifest['packages']:
                if not isinstance(pkg, dict):
                    continue
                
                # Case 1: Direct items in a standard package (e.g., box)
                if 'items' in pkg and isinstance(pkg['items'], list):
                    for item in pkg['items']:
                        if isinstance(item, dict):
                            total += item.get('qty', 0)
                
                # Case 2: Items inside boxes nested within a package (e.g., pallet)
                if 'boxes' in pkg and isinstance(pkg['boxes'], list):
                    for box in pkg['boxes']:
                        if isinstance(box, dict) and 'items' in box and isinstance(box['items'], list):
                            for item in box['items']:
                                if isinstance(item, dict):
                                    total += item.get('qty', 0)
        return total
            
    # Calculate the total item quantity across all filtered shipments
    total_qty = filtered_df['manifest'].apply(calculate_total_qty).sum()
    
    # Return the result as a DataFrame
    return pd.DataFrame({'total_item_units': [total_qty]})