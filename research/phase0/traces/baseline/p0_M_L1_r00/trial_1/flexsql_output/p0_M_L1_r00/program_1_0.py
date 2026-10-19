import pandas as pd
import json

def processing(dfs):
    # Readings table is dfs[0], Devices table is dfs[1]
    readings = dfs[0].copy()
    devices = dfs[1].copy()

    # Parse JSON from string to dict if it's currently a string
    if isinstance(readings['payload'].iloc[0], str):
        readings['payload'] = readings['payload'].apply(json.loads)

    # Extract energy_kwh from the payload dictionary
    # Assuming the structure is {'metrics': {'energy_kwh': ...}}
    readings['energy_kwh'] = readings['payload'].apply(
        lambda x: x.get('metrics', {}).get('energy_kwh', 0)
    )

    # Merge devices and readings on 'device_id'
    merged_df = pd.merge(readings, devices, on='device_id')

    # Filter by site 'north'
    north_devices = merged_df[merged_df['site'] == 'north']

    # Convert recorded_at to datetime to filter by Month and Year
    north_devices['recorded_at'] = pd.to_datetime(north_devices['recorded_at'])
    june_2025_readings = north_devices[
        (north_devices['recorded_at'].dt.year == 2025) & 
        (north_devices['recorded_at'].dt.month == 6)
    ]

    # Calculate total energy
    total_energy = june_2025_readings['energy_kwh'].sum()

    # Return result as a DataFrame, rounded to 2 decimal places
    return pd.DataFrame({'total_energy_kwh': [round(total_energy, 2)]})