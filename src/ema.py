import pandas as pd

def ema(data, window):
    if len(data) < window:
        return pd.Series([None] * len(data))
    return data.ewm(span=window, adjust=False).mean().bfill()  # Using bfill() as recommended
