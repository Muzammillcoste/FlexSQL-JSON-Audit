import pandas as pd
import ast

def processing(dfs):
    # Devices (dfs[0]) and Readings (dfs[1])
    devices = dfs[0]
    readings = dfs[1]

    # Combine tables on device_id
    df = pd.merge(readings, devices, on='device_id')

    # Filter for site 'north' (exact match)
    df = df[df['site'] == 'north'].copy()

    # Filter for June 2025 using a regex (string search)
    df = df[df['recorded_at'].str.contains(r'^2025-06', na=False)].copy()

    # Parse 'payload' and extract 'energy_kwh' from 'metrics'
    def get_energy(row):
        payload = row['payload']
        # Handle empty payloads
        if not payload:
            return 0
        
        # If payload is a string (e.g., representation of a dict), parse it safely
        if isinstance(payload, str):
            try:
                # ast.literal_eval safely parses strings to Python dicts, 
                # supporting the single-quoted format often produced by DBs
                payload_dict = ast.literal_eval(payload)
            except (ValueError, SyntaxError):
                return 0
        else:
            # If already a dict, use as is
            payload_dict = payload
        
        # Navigate safely to metrics
        metrics = payload_dict.get('metrics')
        if isinstance(metrics, dict):
            return metrics.get('energy_kwh', 0)
        return 0
    
    # Calculate energy_kwh for each row
    df['energy_kwh'] = df.apply(get_energy, axis=1)
    
    # Sum the values and round to 2 decimal places
    total_energy = df['energy_kwh'].sum()
    total_energy_rounded = round(float(total_energy), 2)
    
    # Return result as a DataFrame
    return pd.DataFrame({'total_energy_kwh': [total_energy_rounded]})