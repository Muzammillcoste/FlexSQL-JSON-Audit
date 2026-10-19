import pandas as pd
import ast

def processing(dfs):
    # dfs[0] is 'readings', dfs[1] is 'devices'
    readings = dfs[0]
    devices = dfs[1]

    # Merge devices and readings
    merged = pd.merge(readings, devices, on='device_id')

    # Filter by model 'TX-200'
    merged = merged[merged['model'] == 'TX-200']

    # Convert recorded_at to datetime
    merged['recorded_at'] = pd.to_datetime(merged['recorded_at'])

    # Filter for July 2025
    merged = merged[(merged['recorded_at'].dt.year == 2025) & (merged['recorded_at'].dt.month == 7)]

    # Function to extract status and normalize it
    def extract_and_normalize_status(payload_str):
        try:
            # Use ast.literal_eval for parsing the Python dict-like string
            data = ast.literal_eval(payload_str)
            status = data.get('status')
            if status:
                return str(status).lower()
        except:
            pass
        return None

    # Apply extraction and filter for 'fault'
    merged['status_normalized'] = merged['payload'].apply(extract_and_normalize_status)
    faulty_readings = merged[merged['status_normalized'] == 'fault']

    # Count the number of readings
    count = len(faulty_readings)

    # Return as a DataFrame
    return pd.DataFrame({'count': [count]})