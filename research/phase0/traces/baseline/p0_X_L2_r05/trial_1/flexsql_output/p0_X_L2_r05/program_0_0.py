import pandas as pd
import json

def processing(dfs):
    """
    Counts readings from devices of model 'TX-200' recorded in July 2025 (UTC)
    that have a 'fault' status, checking both 'status' and 'state'->'code' fields.
    """
    devices_df = dfs[0]
    readings_df = dfs[1]

    # 1. Get the list of device_id for all devices with the model 'TX-200'
    tx200_devices = devices_df[devices_df['model'] == 'TX-200']['device_id'].unique()

    # 2. Filter readings:
    # - recorded in July 2025
    # - device_id must be in the list of 'TX-200' devices
    # Using '2025-07' to identify July 2025 timestamps
    readings_filtered = readings_df[readings_df['recorded_at'].str.startswith('2025-07')].copy()
    readings_filtered = readings_filtered[readings_filtered['device_id'].isin(tx200_devices)].copy()

    # 3. Parse the 'payload' column from JSON string to check for 'fault' (case-insensitive)
    def check_for_fault(payload_str):
        try:
            data = json.loads(payload_str)
            # Check 'status' field
            if str(data.get('status', '')).lower() == 'fault':
                return True
            # Check 'state' -> 'code' field
            state = data.get('state')
            if isinstance(state, dict):
                if str(state.get('code', '')).lower() == 'fault':
                    return True
            return False
        except (json.JSONDecodeError, TypeError, AttributeError):
            return False

    readings_filtered['is_fault'] = readings_filtered['payload'].apply(check_for_fault)

    # 4. Count the number of 'fault' readings
    count = readings_filtered['is_fault'].sum()

    # Return the result as a DataFrame
    return pd.DataFrame({'result': [count]})