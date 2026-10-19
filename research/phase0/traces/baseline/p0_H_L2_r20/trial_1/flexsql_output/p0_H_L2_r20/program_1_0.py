import pandas as pd
import ast

def processing(dfs):
    devices = dfs[0]
    readings = dfs[1]
    
    # Join the 'devices' and 'readings' tables on the 'device_id' column
    merged = pd.merge(readings, devices, on='device_id')
    
    # Filter the results: model 'TX-200'
    merged = merged[merged['model'] == 'TX-200']
    
    # Filter: recorded in July 2025
    # The recorded_at column uses ISO 8601 formatting, so startswith('2025-07') covers all of July 2025.
    merged = merged[merged['recorded_at'].str.startswith('2025-07')]
    
    # Function to safely parse and extract status.
    # The payload is provided as a string representation of a dictionary.
    # It can have either a top-level 'status' key or a nested 'state' dictionary containing a 'code' key.
    def get_status(p):
        try:
            data = ast.literal_eval(p)
            # Check structure 1: top-level 'status'
            if 'status' in data:
                return str(data['status']).lower()
            # Check structure 2: nested 'state' -> 'code'
            if 'state' in data and isinstance(data['state'], dict) and 'code' in data['state']:
                return str(data['state']['code']).lower()
            return None
        except:
            return None
    
    # Parse payload for status
    merged['extracted_status'] = merged['payload'].apply(get_status)
    
    # Count records that have a 'fault' status
    fault_count = (merged['extracted_status'] == 'fault').sum()
    
    # Return result as a DataFrame
    return pd.DataFrame({'fault_count': [fault_count]})