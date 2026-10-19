import pandas as pd
import json

def processing(dfs):
    v = [float(p['amount']) for p in map(json.loads, dfs[0]['payload']) if p.get('type') == 'purchase']
    return pd.DataFrame({'max': [max(v)]})
