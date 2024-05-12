import pandas as pd

def bollinger_bands(data, window, num_std_dev):
    if len(data) < window:
        return pd.Series([None] * len(data)), pd.Series([None] * len(data))
    sma = data.rolling(window).mean()
    std = data.rolling(window).std()
    upper_band = sma + (std * num_std_dev)
    lower_band = sma - (std * num_std_dev)
    return upper_band.bfill(), lower_band.bfill()
