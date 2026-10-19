import pandas as pd
import json

def processing(dfs):
    n = 0
    for s in dfs[0]['payload']:
        for it in json.loads(s)['items']:
            if it.get('discount'):
                n += 1
    return pd.DataFrame({'n_discounted_items': [n]})
