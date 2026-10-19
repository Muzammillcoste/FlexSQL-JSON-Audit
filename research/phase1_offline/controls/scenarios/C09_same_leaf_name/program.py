import pandas as pd
import json

def processing(dfs):
    n = 0
    for s in dfs[0]['payload']:
        c = json.loads(s).get('coupon')
        if isinstance(c, dict) and c.get('code', '').startswith('C1'):
            n += 1
    return pd.DataFrame({'n': [n]})
