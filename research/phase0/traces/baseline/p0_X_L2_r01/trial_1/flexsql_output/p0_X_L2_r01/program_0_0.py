import pandas as pd
import ast

def processing(dfs):
    """
    Counts the number of readings from 'TX-200' devices in July 2025 with 'fault' status.
    """
    readings = dfs[0]
    devices = dfs[1]

    # 1. Join the 'devices' and 'readings' tables on the 'device_id' column.
    merged = pd.merge(readings, devices, on='device_id')

    # 2. Filter the results to include only records where the 'model' is 'TX-200'.
    merged = merged[merged['model'] == 'TX-200']

    # 3. Filter the 'recorded_at' timestamp for July 2025.
    # Assuming recorded_at is in 'YYYY-MM-DDTHH:MM:SSZ' format.
    merged = merged[merged['recorded_at'].str.startswith('2025-07', na=False)]

    # 4. Parse the payload and filter for 'fault' status (case-insensitive).
    def is_fault(payload_str):
        try:
            # Using ast.literal_eval to safely parse Python dict string representation.
            payload = ast.literal_eval(payload_str)
            # Safely get status, convert to string, handle case insensitivity.
            status = str(payload.get('status', '')).lower()
            return status == 'fault'
        except (ValueError, SyntaxError, TypeError, AttributeError):
            return False

    mask = merged['payload'].apply(is_fault)
    filtered_df = merged[mask]

    # 5. Count the number of resulting reading entries.
    count = len(filtered_df)
    
    return pd.DataFrame({'count': [count]})