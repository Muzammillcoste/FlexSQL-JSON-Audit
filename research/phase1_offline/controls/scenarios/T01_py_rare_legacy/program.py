import pandas as pd
import json

def processing(dfs):
    df = dfs[0][dfs[0]['plant'] == 'p1']
    v = [json.loads(s).get('pressure') for s in df['payload']]
    v = [x for x in v if x is not None]
    return pd.DataFrame({'avg_kpa': [round(sum(v) / len(v), 2)]})
