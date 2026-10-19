import pandas as pd
import json

def processing(dfs):
    t = 0.0
    for s in dfs[0]['payload']:
        p = json.loads(s)
        if p.get('type') == 'purchase':
            t += float(p['amount'])
    return pd.DataFrame({'total': [round(t, 2)]})
