import pandas as pd
import json

def processing(dfs):
    hr = []
    for s in dfs[0][dfs[0]['visit_date'].str.startswith('2025-05')]['record']:
        p = json.loads(s)
        if 'vitals' in p:
            hr.append(p['vitals']['hr'])
        else:
            hr += [o['val'] for o in p.get('obs', []) if o['code'] == 'HR']
    return pd.DataFrame({'avg_hr': [round(sum(hr) / len(hr), 1)]})
