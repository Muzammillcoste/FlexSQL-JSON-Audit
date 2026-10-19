import pandas as pd
import ast

def processing(dfs):
    # Access the DataFrames from the input list
    df_readings = dfs[0]
    df_devices = dfs[1]
    
    # 1. Identify device_ids in the 'north' site
    north_devices = df_devices[df_devices['site'] == 'north']['device_id'].unique()
    
    # 2. Filter readings to include only those from 'north' devices in June 2025
    # The 'recorded_at' field is a string, so we use string matching for the month
    mask = df_readings['device_id'].isin(north_devices) & \
           df_readings['recorded_at'].str.startswith('2025-06')
    
    selected_readings = df_readings[mask].copy()
    
    # 3. Parse the 'payload' column to extract the 'energy_kwh' value
    def get_energy(payload_str):
        try:
            # The payload is stored as a string representation of a dictionary
            # use ast.literal_eval to safely parse it
            payload = ast.literal_eval(payload_str)
            # Extract the nested 'energy_kwh' value from the 'metrics' dictionary
            return float(payload.get('metrics', {}).get('energy_kwh', 0.0))
        except (ValueError, SyntaxError):
            # In case of malformed payload, return 0
            return 0.0
            
    selected_readings['energy'] = selected_readings['payload'].apply(get_energy)
    
    # 4. Compute the sum and round to 2 decimal places
    total_energy = round(selected_readings['energy'].sum(), 2)
    
    # Return the final result as a DataFrame
    return pd.DataFrame({'total_energy_kwh': [total_energy]})