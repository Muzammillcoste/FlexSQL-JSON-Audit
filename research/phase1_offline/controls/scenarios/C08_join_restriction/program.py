import pandas as pd
import json

def processing(dfs):
    df = dfs[0].merge(dfs[1][dfs[1]['region'] == 'west'], on='site')
    v = [json.loads(s)['temp_c'] for s in df['payload']]
    return pd.DataFrame({'avg_temp_c': [round(sum(v) / len(v), 2)]})
