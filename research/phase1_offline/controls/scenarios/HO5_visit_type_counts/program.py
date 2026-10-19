import pandas as pd
import json

def processing(dfs):
    c = {}
    for s in dfs[0]['record']:
        t = json.loads(s).get('visit_type')
        c[t] = c.get(t, 0) + 1
    return pd.DataFrame({'visit_type': list(c), 'n': list(c.values())})
