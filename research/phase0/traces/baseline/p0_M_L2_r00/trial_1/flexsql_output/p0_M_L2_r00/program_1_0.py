import pandas as pd
import ast

def processing(dfs):
    # Extract the relevant dataframes
    # dfs[0] is 'devices', dfs[1] is 'readings'
    devices_df = dfs[0]
    readings_df = dfs[1]

    # 1. Get device_ids for model 'TX-200'
    # The schema of devices_df is ['device_id', 'model']
    target_device_ids = devices_df[devices_df['model'] == 'TX-200']['device_id'].unique()

    # 2. Filter readings
    # The schema of readings_df is ['device_id', 'recorded_at', 'payload']
    # Filter by device_id
    filtered_readings = readings_df[readings_df['device_id'].isin(target_device_ids)].copy()

    # Filter by date (July 2025)
    # The 'recorded_at' column contains ISO strings like '2025-05-01T00:05:19Z'
    # We filter by the beginning of the string to match '2025-07'
    filtered_readings = filtered_readings[filtered_readings['recorded_at'].str.startswith('2025-07')]

    # 3. Parse 'payload' string and check 'status'
    def get_status(payload_str):
        try:
            # ast.literal_eval is robust against potential variations in JSON/Python dict strings
            data = ast.literal_eval(payload_str)
            # Safely get the status, convert to string, and force lowercase for case-insensitivity
            return str(data.get('status', '')).lower()
        except (ValueError, SyntaxError, TypeError, AttributeError):
            # Return empty string if payload format is unexpected
            return ''

    # Extract the status from the payload
    filtered_readings['status'] = filtered_readings['payload'].apply(get_status)

    # 4. Count readings where status is 'fault'
    # 'Status values are case-insensitive' is handled by str.lower() already
    fault_count = (filtered_readings['status'] == 'fault').sum()

    # 5. Return the result as a DataFrame
    return pd.DataFrame({'count': [fault_count]})