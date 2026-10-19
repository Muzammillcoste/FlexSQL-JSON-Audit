import pandas as pd
import ast

def processing(dfs):
    # Unpack DataFrames
    df_readings = dfs[0]
    df_devices = dfs[1]

    # Inner join to combine readings with device info
    merged = pd.merge(df_readings, df_devices, on='device_id')

    # Filter for model 'TX-200'
    merged = merged[merged['model'] == 'TX-200'].copy()

    # Parse recorded_at and filter for July 2025 (UTC)
    merged['recorded_at'] = pd.to_datetime(merged['recorded_at'])
    
    # Filter for July 2025
    merged = merged[
        (merged['recorded_at'].dt.year == 2025) & 
        (merged['recorded_at'].dt.month == 7)
    ]

    # Helper function to parse payload and check 'fault' status
    def check_fault(payload_str):
        if not isinstance(payload_str, str):
            return False
        try:
            # Using ast.literal_eval to safely parse string that looks like a 
            # Python dictionary (handles single quotes allowed in representation)
            data = ast.literal_eval(payload_str)
            
            # Ensure it parsed as a dictionary and check 'status' key
            if isinstance(data, dict):
                # Ensure status is treated as a string for case-insensitive comparison
                status = str(data.get('status', ''))
                return status.lower() == 'fault'
        except (ValueError, SyntaxError):
            # If payload is invalid or not in the expected format, treat as not a 'fault'
            return False
        return False

    # Apply the check to each payload row
    is_fault = merged['payload'].apply(check_fault)
    fault_count = is_fault.sum()
    
    # Return as a DataFrame containing the resulting count
    return pd.DataFrame({'fault_count': [fault_count]})