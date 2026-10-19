import pandas as pd
import json

def processing(dfs):
    n = 0
    for s in dfs[0]['payload']:
        p = json.loads(s)
        if isinstance(p.get('coupon'), dict):
            n += 1
    return pd.DataFrame({'n': [n]})
