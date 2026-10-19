import pandas as pd
import json

def processing(dfs):
    """
    Parses the readings for 'TX-200' devices in July 2025 (UTC)
    to count how many reported a 'fault' status.
    """
    devices = dfs[0]
    readings = dfs[1]

    # Join the 'readings' and 'devices' tables
    df = readings.merge(devices, on='device_id')

    # Filter for model 'TX-200'
    df = df[df['model'] == 'TX-200']

    # Narrow down to records in July 2025
    df['recorded_at'] = pd.to_datetime(df['recorded_at'])
    df = df[(df['recorded_at'].dt.year == 2025) & (df['recorded_at'].dt.month == 7)]

    # Function to parse JSON payload and check for 'fault' status
    def is_faulty(payload_str):
        try:
            p = json.loads(payload_str)
            
            # Check top-level 'status'
            status = p.get('status')
            if status and str(status).lower() == 'fault':
                return True
                
            # Check nested 'state.code'
            state = p.get('state')
            if isinstance(state, dict):
                code = state.get('code')
                if code and str(code).lower() == 'fault':
                    return True
                    
            return False
        except (json.JSONDecodeError, TypeError):
            # In case of malformed JSON or other unexpected data
            return False

    # Apply the status check
    df['is_fault'] = df['payload'].apply(is_faulty)

    # Return the count of records with 'fault' status
    fault_count = df['is_fault'].sum()
    
    return pd.DataFrame({'fault_count': [fault_count]})