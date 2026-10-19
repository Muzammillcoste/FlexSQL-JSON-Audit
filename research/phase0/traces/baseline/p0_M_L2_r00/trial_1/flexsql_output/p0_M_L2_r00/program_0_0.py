import pandas as pd
import json

def processing(dfs):
    # Load the dataframes
    devices = dfs[0]
    readings = dfs[1]

    # Merge the devices and readings tables on 'device_id'
    merged = pd.merge(readings, devices, on='device_id')

    # Filter by model 'TX-200'
    filtered = merged[merged['model'] == 'TX-200'].copy()

    # Further restrict the records to those where the 'recorded_at' 
    # timestamp falls within the month of July 2025
    filtered['recorded_at'] = pd.to_datetime(filtered['recorded_at'])
    filtered = filtered[
        (filtered['recorded_at'].dt.year == 2025) & 
        (filtered['recorded_at'].dt.month == 7)
    ]

    # Parse the 'payload' JSON column and extract the 'status'
    def get_status(payload_str):
        try:
            # Parse the string into a dictionary
            payload_dict = json.loads(payload_str)
            # Return the status value, defaulting to an empty string if missing
            return payload_dict.get('status', '').lower()
        except (json.JSONDecodeError, AttributeError):
            return ''

    filtered['status'] = filtered['payload'].apply(get_status)

    # Filter for 'fault' (case-insensitive, as already normalized to lower)
    fault_readings = filtered[filtered['status'] == 'fault']

    # Return the count of these records as a DataFrame
    return pd.DataFrame({'count': [len(fault_readings)]})