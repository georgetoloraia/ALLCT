import pandas as pd

def vwap(prices, volumes):
    if volumes.sum() == 0:
        return pd.Series([None]*len(prices))
    cumulative_vwap = (prices * volumes).cumsum() / volumes.cumsum()
    return cumulative_vwap
