import pandas as pd

def ema(data, window):
    return data.ewm(span=window, adjust=False).mean()

def trix(data, window):
    if data.isnull().any():
        # Directly use ffill() and bfill() instead of fillna(method='ffill/bfill')
        data = data.ffill().bfill()
    single_ema = ema(data, window)
    double_ema = ema(single_ema, window)
    triple_ema = ema(double_ema, window)
    trix = 100 * (triple_ema.diff() / triple_ema)
    # Apply ffill() and bfill() directly to handle NaNs in the final result
    return trix.ffill().bfill()

