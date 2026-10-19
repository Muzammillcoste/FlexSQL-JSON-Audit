import pandas as pd
import json

def processing(dfs):
    carriers = dfs[0]
    shipments = dfs[1]

    # 1. Identify air carriers
    # Filter for carriers where transport_mode is 'air'
    air_carriers = carriers[carriers['transport_mode'] == 'air']['carrier_code'].unique()

    # 2. Filter shipments
    # Only keep shipments handled by the identified 'air' carriers
    shipments_air = shipments[shipments['carrier_code'].isin(air_carriers)].copy()

    # 3. Parse and calculate transit times
    durations = []
    
    for _, row in shipments_air.iterrows():
        try:
            # Parse tracking JSON string
            tracking = json.loads(row['tracking'])                
            
            # Find the 'DELIVERED' event within the events list
            events = tracking.get('events', [])
            if not isinstance(events, list):
                continue
                
            delivered_event = next((ev for ev in events if ev.get('code') == 'DELIVERED'), None)
            if not delivered_event:
                continue
                
            # Convert timestamps
            # created_at is naive, delivered_at is timezone-aware from the Z suffix
            created_at = pd.to_datetime(row['created_at'])
            delivered_at = pd.to_datetime(delivered_event.get('at'))
            
            # Ensure both are timezone-aware in UTC before subtracting
            if created_at.tzinfo is None:
                created_at = created_at.tz_localize('UTC')
            if delivered_at.tzinfo is None:
                delivered_at = delivered_at.tz_localize('UTC')
                
            # Calculate duration in hours
            duration = (delivered_at - created_at).total_seconds() / 3600
            durations.append(duration)                
        except Exception:
            # Skip rows where parsing or calculation fails
            continue
            
    # 4. Calculate average and round
    if not durations:
        # Return 0.0 if no valid delivered shipments are found
        return pd.DataFrame({'avg_transit_time_hours': [0.0]})
        
    avg_result = sum(durations) / len(durations)
    return pd.DataFrame({'avg_transit_time_hours': [round(avg_result, 1)]})