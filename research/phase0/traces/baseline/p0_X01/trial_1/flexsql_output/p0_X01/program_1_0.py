import ast
import pandas as pd

def processing(dfs):
    # Load the shipments DataFrame
    df = dfs[0].copy()
    
    # 1. Convert 'created_at' column to datetime objects for accurate filtering
    df['created_at'] = pd.to_datetime(df['created_at'])
    
    # 2. Filter for shipments created in May 2025
    may_2025_df = df[(df['created_at'].dt.year == 2025) & (df['created_at'].dt.month == 5)]
    
    total_physical_weight_kg = 0.0
                
    # 3. Iterate through shipments to parse the manifest and calculate weight
    for manifest_item in may_2025_df['manifest']:
        # Skip empty manifest entries
        if pd.isna(manifest_item):
            continue
            
        # Ensure we have a workable manifest dictionary
        # The manifest column data might have been loaded as a JSON string or as a dict
        if isinstance(manifest_item, str):
            try:
                # Use literal_eval for dict strings, which handles single-quoted keys/values
                manifest = ast.literal_eval(manifest_item)
            except (ValueError, SyntaxError):
                continue
        elif isinstance(manifest_item, dict):
            manifest = manifest_item
        else:
            continue
            
        # Get the list of packages from the manifest
        # manifest should be a dict if it was parsed correctly
        if not isinstance(manifest, dict):
            continue
            
        packages = manifest.get('packages', [])
        
        # 4. Calculate physical weight for each package
        if isinstance(packages, list):
            for pkg in packages:
                if not isinstance(pkg, dict):
                    continue
                                    
                # Using the priority: gross_weight_kg -> weight_kg -> gross_weight_g -> weight_g
                # This ensures we take the most specific physical weight available for the package type.
                # Gross weight takes precedence as it is the package's total physical weight.
                if 'gross_weight_kg' in pkg:
                    total_physical_weight_kg += float(pkg['gross_weight_kg'])
                elif 'weight_kg' in pkg:
                    total_physical_weight_kg += float(pkg['weight_kg'])
                elif 'gross_weight_g' in pkg:
                    try:
                        total_physical_weight_kg += float(pkg['gross_weight_g']) / 1000.0
                    except:
                        continue
                elif 'weight_g' in pkg:
                    try:
                        total_physical_weight_kg += float(pkg['weight_g']) / 1000.0
                    except:
                        continue
            
    # 5. Return the total weight as a DataFrame, rounded to 1 decimal place
    return pd.DataFrame({'total_weight_kg': [round(total_physical_weight_kg, 1)]})