import pandas as pd
import json

def processing(dfs):
    n = sum(1 for s in dfs[0]['payload'] if json.loads(s).get('gift_wrap') is True)
    return pd.DataFrame({'n': [n]})
