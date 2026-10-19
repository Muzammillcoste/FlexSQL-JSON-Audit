import pandas as pd
import json

def processing(dfs):
    df = dfs[0].merge(dfs[1], on='clinic_id')
    df = df[(df['area'] == 'north') & df['visit_date'].str.startswith('2025-05')]
    hr = []
    for s in df['record']:
        try:
            hr.append(json.loads(s)['vitals']['hr'])
        except (KeyError, TypeError):
            pass
    return pd.DataFrame({'avg_hr': [round(sum(hr) / len(hr), 1)]})
