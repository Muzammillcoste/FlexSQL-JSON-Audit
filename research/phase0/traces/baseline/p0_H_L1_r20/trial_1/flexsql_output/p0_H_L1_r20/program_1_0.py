import pandas as pd
import json

def processing(dfs):
    readings = dfs[0]
    devices = dfs[1]
    
    # 1. Join 'devices' and 'readings' tables using the 'device_id' column.
    df = pd.merge(readings, devices, on='device_id')
    
    # 2. Filter the joined results to include only records where the 'site' 
    #    column in the 'devices' table is 'north' and the 'recorded_at' 
    #    timestamp in the 'readings' table falls within June 2025.
    df['recorded_at'] = pd.to_datetime(df['recorded_at'])
    df = df[
        (df['site'] == 'north') & 
        (df['recorded_at'].dt.year == 2025) & 
        (df['recorded_at'].dt.month == 6)
    ].copy()
    
    # 3. Parse the 'payload' column in the 'readings' table to extract 
    #    energy consumption values; if a reading is given in Wh, 
    #    convert it to kWh by dividing by 1000.
    def extract_energy(payload):
        if pd.isna(payload) or payload == "":
            return 0.0
        
        try:
            data = json.loads(payload)
            
            # Type 1: "metrics" structure
            if isinstance(data, dict) and 'metrics' in data and 'energy_kwh' in data['metrics']:
                return float(data['metrics']['energy_kwh'])
            
            # Type 2: "data" -> "readings" structure
            if isinstance(data, dict) and 'data' in data and isinstance(data['data'], dict) and 'readings' in data['data']:
                for item in data['data']['readings']:
                    if isinstance(item, dict) and item.get('k') == 'energy':
                        val = item.get('v')
                        unit = item.get('u')
                        if unit == 'Wh':
                            return float(val) / 1000.0
                        elif unit == 'kWh':
                            return float(val)
            return 0.0
        except (json.JSONDecodeError, ValueError, TypeError):
            return 0.0

    # Calculate energy for each reading
    df['energy_kwh'] = df['payload'].apply(extract_energy)
    
    # 4. Calculate the total energy consumption by summing the normalized 
    #    values (in kWh) and 5. Round the sum to 2 decimal places.
    total = round(df['energy_kwh'].sum(), 2)
    
    # Return as a DataFrame
    return pd.DataFrame({'total_energy_kwh': [total]})