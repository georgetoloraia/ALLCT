import pandas as pd

def ema(data, window):
    return data.ewm(span=window, adjust=False).mean()

def trix(data, window):
    if data.isnull().any():
        data = data.fillna(method='bfill')  # Handle NaN values
    single_ema = ema(data, window)
    double_ema = ema(single_ema, window)
    triple_ema = ema(double_ema, window)
    trix = 100 * (triple_ema.diff() / triple_ema)
    return trix.fillna(0)  # Handle division by zero if any
