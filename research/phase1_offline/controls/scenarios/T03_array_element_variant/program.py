import pandas as pd
import json

def processing(dfs):
    q = 0
    for s in dfs[0]['payload']:
        for it in json.loads(s)['items']:
            q += it.get('qty', 0)
    return pd.DataFrame({'units': [q]})
