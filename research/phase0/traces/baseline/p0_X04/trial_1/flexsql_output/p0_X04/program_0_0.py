import pandas as pd
import ast
import json

def processing(dfs):
    shipments = dfs[0]
    carriers = dfs[1]

    # Join the 'shipments' table with the 'carriers' table
    df = pd.merge(shipments, carriers, on='carrier_code', how='inner')

    # Filter for shipments handled by carriers with 'air' transport mode
    df = df[df['transport_mode'] == 'air'].copy()

    # Function to extract the 'DELIVERED' event timestamp
    def get_delivered_time(tracking_str):
        if pd.isna(tracking_str):
            return None
        # Try parsing JSON first, fallback to literal_eval for Python representation
        try:
            try:
                tracking = json.loads(tracking_str)
            except (json.JSONDecodeError, TypeError):
                # Handle cases where tracking uses single quotes
                tracking = ast.literal_eval(tracking_str)
            
            for event in tracking.get('events', []):
                if event['code'] == 'DELIVERED':
                    return event['at']
        except Exception:
            return None
        return None

    # Apply delivery time extraction to each row
    df['delivered_at'] = df['tracking'].apply(get_delivered_time)

    # Filter to only include shipments that have a 'DELIVERED' event
    df_delivered = df.dropna(subset=['delivered_at']).copy()
    
    # Convert created_at and delivered_at to UTC-aware datetime objects
    # utc=True ensures both are treated as aware (UTC) and allows for subtraction
    df_delivered['created_at'] = pd.to_datetime(df_delivered['created_at'], utc=True)
    df_delivered['delivered_at'] = pd.to_datetime(df_delivered['delivered_at'], utc=True)
    
    # Calculate transit time in hours
    df_delivered['transit_time_hours'] = (df_delivered['delivered_at'] - df_delivered['created_at']).dt.total_seconds() / 3600
    
    # Calculate the average transit time
    avg_transit_time = df_delivered['transit_time_hours'].mean()
    
    # Round to 1 decimal place (handle potential NaN if no data exists)
    if pd.isna(avg_transit_time):
        result = 0.0
    else:
        result = round(avg_transit_time, 1)
    
    return pd.DataFrame({'average_transit_time': [result]})