import numpy as np
import pandas as pd

def wma(data, window):
    if len(data) < window:
        return pd.Series([None] * len(data))
    weights = np.arange(1, window + 1)
    return data.rolling(window).apply(lambda prices: np.dot(prices, weights) / weights.sum(), raw=True).bfill()
