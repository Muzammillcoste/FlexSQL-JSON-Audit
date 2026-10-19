import pandas as pd
import json

def processing(dfs):
    df = dfs[0].copy()
    df['t'] = df['payload'].apply(lambda s: json.loads(s).get('temp_c'))
    df = df[df['site'] == 'a']
    return pd.DataFrame({'avg_temp_c': [round(df['t'].mean(), 2)]})
