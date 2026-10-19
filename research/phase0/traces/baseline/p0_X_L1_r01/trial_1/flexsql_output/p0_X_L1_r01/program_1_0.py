import pandas as pd
import json

def processing(dfs):
    # Load the dataframes
    devices = dfs[0]
    readings = dfs[1]

    # Filter devices located at the 'north' site
    north_devices = devices[devices['site'] == 'north']

    # Merge readings with the filtered devices to get readings for north site
    # Inner merge automatically filters for device_ids in both
    merged = pd.merge(readings, north_devices, on='device_id')

    # Filter readings recorded in June 2025 (UTC)
    june_readings = merged[merged['recorded_at'].str.startswith('2025-06')]

    # Function to parse the payload string and extract 'energy_kwh'
    def get_energy(payload):
        try:
            if isinstance(payload, str):
                payload_dict = json.loads(payload)
            else:
                payload_dict = payload
            # Navigate to 'metrics' -> 'energy_kwh'
            return payload_dict.get('metrics', {}).get('energy_kwh', 0)
        except (json.JSONDecodeError, AttributeError, TypeError):
            return 0

    # Apply the function to extract 'energy_kwh'
    june_readings = june_readings.copy()
    june_readings['energy_kwh'] = june_readings['payload'].apply(get_energy)

    # Calculate sum of energy_kwh
    total_energy = june_readings['energy_kwh'].sum()

    # Round to 2 decimal places
    total_energy_rounded = round(total_energy, 2)

    # Return the result as a DataFrame
    return pd.DataFrame({'total_energy_consumed_kwh': [total_energy_rounded]})