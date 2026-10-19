import pandas as pd
import json

def processing(dfs):
    n = 0
    for s in dfs[0]['record']:
        a = json.loads(s).get('allergies')
        if a:
            n += 1
    return pd.DataFrame({'n': [n]})
