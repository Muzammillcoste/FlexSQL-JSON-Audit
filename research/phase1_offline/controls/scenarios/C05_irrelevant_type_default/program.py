import pandas as pd
import json

def processing(dfs):
    t = sum(float(json.loads(s).get('amount', 0)) for s in dfs[0]['payload'])
    return pd.DataFrame({'total': [round(t, 2)]})
