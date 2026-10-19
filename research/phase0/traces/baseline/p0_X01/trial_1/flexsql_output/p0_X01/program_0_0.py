import pandas as pd
import ast

def processing(dfs):
    df = dfs[0]
    
    # 1. Ensure created_at is converted to datetime
    df['created_at'] = pd.to_datetime(df['created_at'])
    
    # 2. Filter for May 2025
    may_2025 = df[(df['created_at'].dt.year == 2025) & (df['created_at'].dt.month == 5)].copy()
    
    # Helper to recursively extract weights from the manifest structure
    def extract_weights(obj):
        total = 0.0
        if isinstance(obj, list):
            for item in obj:
                total += extract_weights(item)
        elif isinstance(obj, dict):
            # Check for physical weight in kg or g
            if 'weight_kg' in obj:
                total += obj['weight_kg']
            elif 'weight_g' in obj:
                total += obj['weight_g'] / 1000.0
                
            # Recursively search all values in the dict for nested structures (like pallet boxes)
            for value in obj.values():
                total += extract_weights(value)
        return total
    
    total_physical_weight = 0.0
    
    # 3. Iterate through relevant shipments and parse manifest
    for _, row in may_2025.iterrows():
        manifest = row['manifest']
        
        # Manifest can be a string representation or a dict; parse if it's a string
        if isinstance(manifest, str):
            try:
                manifest = ast.literal_eval(manifest)
            except:
                continue
        
        # 4. Extract weights from the packages list
        # Ensure we only process 'packages' to avoid top-level billable weight
        if isinstance(manifest, dict) and 'packages' in manifest:
            total_physical_weight += extract_weights(manifest['packages'])
            
    # 5. Return the result as a DataFrame, rounded to 1 decimal place
    return pd.DataFrame({'total_weight_kg': [round(total_physical_weight, 1)]})