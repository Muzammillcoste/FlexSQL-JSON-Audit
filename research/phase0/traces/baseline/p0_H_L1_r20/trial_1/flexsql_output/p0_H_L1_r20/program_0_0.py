import pandas as pd
import ast

def processing(dfs):
    # The DataFrame from SQL Query 1 ('readings') is at dfs[0]
    # The DataFrame from SQL Query 2 ('devices') is at dfs[1]
    readings = dfs[0]
    devices = dfs[1]

    # 1. Join the 'devices' and 'readings' tables on the 'device_id' column
    df = pd.merge(readings, devices, on='device_id')

    # 2. Filter the joined results for devices located at the 'north' site
    df = df[df['site'] == 'north'].copy()

    # 3. Further filter the results to include only readings recorded during June 2025
    # The recorded_at column is in ISO 8601 format (e.g., '2025-05-01T00:05:19Z')
    df['recorded_at'] = pd.to_datetime(df['recorded_at'])
    df = df[(df['recorded_at'] >= '2025-06-01') & (df['recorded_at'] < '2025-07-01')]

    # 4. Extract/Normalize the energy consumption value from the 'payload' field
    def get_energy(payload):
        # Payload can be a JSON-formatted string or a string representation of a Python dict
        if isinstance(payload, str):
            try:
                # ast.literal_eval is safe for parsing Python literal structures
                payload = ast.literal_eval(payload)
            except:
                return 0.0
        
        # Now payload should be a dictionary
        if isinstance(payload, dict):
            # Structure 1: {'metrics': {'energy_kwh': ...}}
            if 'metrics' in payload and 'energy_kwh' in payload['metrics']:
                return float(payload['metrics']['energy_kwh'])
            
            # Structure 2: {'data': {'readings': [{'k': 'energy', 'v': ..., 'u': ...}, ...]}}
            if 'data' in payload and 'readings' in payload['data']:
                data_readings = payload['data']['readings']
                if isinstance(data_readings, list):
                    for item in data_readings:
                        if isinstance(item, dict) and item.get('k') == 'energy':
                            val = item.get('v')
                            unit = item.get('u')
                            # Handle normalization: 1 kWh = 1000 Wh
                            if unit == 'Wh':
                                return float(val) / 1000.0
                            elif unit == 'kWh':
                                return float(val)
        return 0.0

    # Apply the extraction and normalization function
    df['energy'] = df['payload'].apply(get_energy)

    # 5. Calculate the sum of these energy values
    total_energy = df['energy'].sum()

    # 6. Round the resulting total energy consumption to 2 decimal places
    total_energy_kwh = round(total_energy, 2)
    
    # Return the result as a Pandas DataFrame
    return pd.DataFrame({'total_energy_kwh': [total_energy_kwh]})