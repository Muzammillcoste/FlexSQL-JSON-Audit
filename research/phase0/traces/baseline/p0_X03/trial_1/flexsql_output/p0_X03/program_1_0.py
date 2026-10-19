import pandas as pd
import json

def processing(dfs):
    # Load the shipments table from the first DataFrame
    df = dfs[0].copy()
    
    # Convert created_at to datetime objects for easy filtering
    df['created_at'] = pd.to_datetime(df['created_at'])
    
    # Filter for shipments created in June 2025
    df_june = df[(df['created_at'].dt.year == 2025) & (df['created_at'].dt.month == 6)].copy()
    
    # Define a helper function to check for 'DELIVERED' status in the JSON string
    def has_delivered_event(tracking_str):
        try:
            # Parse the JSON string
            data = json.loads(tracking_str)
            # Extract events list
            events = data.get('events', [])
            # Check if any event has the code 'DELIVERED'
            return any(event.get('code') == 'DELIVERED' for event in events)
        except (json.JSONDecodeError, TypeError, AttributeError):
            # If tracking data is malformed or missing, assume not delivered
            return False
            
    # Apply the check along the tracking column
    delivered_mask = df_june['tracking'].apply(has_delivered_event)
    
    # Count the number of shipments that are delivered
    count = delivered_mask.sum()
    
    # Return the result as a DataFrame
    return pd.DataFrame({'delivered_shipments_in_june_2025': [count]})