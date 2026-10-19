import pandas as pd
import ast

def processing(dfs):
    """
    Calculates the total energy consumed in kWh for devices at the 'north' site in June 2025.
    """
    readings = dfs[0]
    devices = dfs[1]

    # 1. Identify all device_id values from the devices table where the site column exactly matches 'north'.
    north_devices = devices[devices['site'] == 'north']['device_id'].unique()

    # 2. Filter the readings table
    # - Filter for readings from June 2025 (recorded_at starts with '2025-06')
    # - Filter by devices located at the 'north' site
    readings_filtered = readings[
        readings['recorded_at'].astype(str).str.startswith('2025-06') &
        readings['device_id'].isin(north_devices)
    ].copy()

    # 3. Parse energy_kwh from the payload string
    def get_energy_kwh(payload_str):
        try:
            # Use ast.literal_eval for safe evaluation of stringified Python dictionaries
            payload_dict = ast.literal_eval(payload_str)
            # Extract the 'energy_kwh' value from the 'metrics' directory
            return payload_dict.get('metrics', {}).get('energy_kwh', 0.0)
        except Exception:
            # Return 0.0 for any parsing or access failures
            return 0.0

    # Apply the parsing function
    readings_filtered['energy_kwh'] = readings_filtered['payload'].apply(get_energy_kwh)

    # 4. Calculate the sum of energy_kwh and round to 2 decimal places
    total_energy = readings_filtered['energy_kwh'].sum()
    total_energy_rounded = round(float(total_energy), 2)

    # 5. Return the result in a DataFrame structure
    return pd.DataFrame({'total_energy_consumed_kwh': [total_energy_rounded]})