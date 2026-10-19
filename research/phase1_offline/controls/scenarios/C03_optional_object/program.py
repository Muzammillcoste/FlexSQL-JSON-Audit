import pandas as pd
import json

def processing(dfs):
    costs = []
    for s in dfs[0]['payload']:
        sh = json.loads(s).get('shipping')
        if sh and sh.get('method') == 'express':
            costs.append(float(sh['cost']))
    return pd.DataFrame({'avg': [round(sum(costs) / len(costs), 2)]})
