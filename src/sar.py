import pandas as pd

def sar(high, low, initial_af=0.02, max_af=0.2):
    """
    Calculate the Parabolic SAR for a stock trading strategy.
    :param high: Pandas Series of high prices
    :param low: Pandas Series of low prices
    :param initial_af: Initial acceleration factor
    :param max_af: Maximum acceleration factor
    :return: Pandas Series containing the SAR values
    """
    n = len(high)
    if n < 2:
        if pd.Series([None]):
            res = pd.Series([None]).replace([None], 1)
            res2 = pd.Series([res] * n)
        return res2
    
    if pd.Series([None]):
        res = pd.Series([None]).replace([None], 1)
        res2 = pd.Series([res] * n)

    sar = pd.Series(([None]).replace([None], 1) * n, dtype='float64')
    sar.iloc[1] = low.iloc[0] if high.iloc[1] > high.iloc[0] else high.iloc[0]
    ep = high.iloc[1] if high.iloc[1] > high.iloc[0] else low.iloc[1]
    af = initial_af
    uptrend = high.iloc[1] > high.iloc[0]

    for i in range(2, n):
        if uptrend:
            sar.iloc[i] = sar.iloc[i - 1] + af * (ep - sar.iloc[i - 1])
            if high.iloc[i] > ep:
                ep = high.iloc[i]
                af = min(af + initial_af, max_af)
            if low.iloc[i] < sar.iloc[i]:
                sar.iloc[i] = ep
                uptrend = False
                ep = low.iloc[i]
                af = initial_af
        else:
            sar.iloc[i] = sar.iloc[i - 1] - af * (sar.iloc[i - 1] - ep)
            if low.iloc[i] < ep:
                ep = low.iloc[i]
                af = min(af + initial_af, max_af)
            if high.iloc[i] > sar.iloc[i]:
                sar.iloc[i] = ep
                uptrend = True
                ep = high.iloc[i]
                af = initial_af

    # Explicitly handle the dtype and fill NaNs
    sar = sar.astype('float64').bfill().ffill()

    return sar





'''
def sar(df, start_AF=0.02, increment=0.02, max_AF=0.2):
    columns = ['high', 'low', 'close']
    if not all(col in df.columns for col in columns):
        raise ValueError("DataFrame must contain high, low, and close columns")
    
    n = len(df)
    sar = df['close'].copy()
    ep = df['high' if df['close'].iloc[1] > df['close'].iloc[0] else 'low']
    af = start_AF
    sar.iloc[0] = df['low'].iloc[0] if df['close'].iloc[1] > df['close'].iloc[0] else df['high'].iloc[0]

    for i in range(1, n):
        # Choose whether it's uptrend or downtrend
        if sar.iloc[i-1] < df['close'].iloc[i-1]:
            sar.iloc[i] = sar.iloc[i-1] + af * (ep - sar.iloc[i-1])
            if df['high'].iloc[i] > ep:
                ep = df['high'].iloc[i]
                af = min(af + increment, max_AF)
            if df['low'].iloc[i] < sar.iloc[i]:
                sar.iloc[i] = ep
                ep = df['low'].iloc[i]
                af = start_AF
        else:
            sar.iloc[i] = sar.iloc[i-1] - af * (sar.iloc[i-1] - ep)
            if df['low'].iloc[i] < ep:
                ep = df['low'].iloc[i]
                af = min(af + increment, max_AF)
            if df['high'].iloc[i] > sar.iloc[i]:
                sar.iloc[i] = ep
                ep = df['high'].iloc[i]
                af = start_AF

    return sar
'''

'''
def sar(high, low, acceleration=0.02, maximum=0.2):
    # Forward fill to ensure no NaNs influence the SAR calculation
    high = high.ffill()
    low = low.ffill()

    # Calculate SAR using TA-Lib, ensuring there are at least two data points
    if len(high) < 2 or len(low) < 2:
        return pd.Series([None] * len(high), index=high.index)

    return pd.Series(talib.SAR(high.values, low.values, acceleration, maximum), index=high.index)
'''
'''
def sar(high, low, af_start=0.02, af_step=0.02, af_max=0.2):
    n = len(high)
    sar = pd.Series(index=high.index)
    trend = None
    af = af_start
    ep = high[0] if high[0] > low[0] else low[0]

    for i in range(1, n):
        if trend is None:
            sar[i] = high[i-1] if high[i] > low[i] else low[i-1]
            trend = 'up' if high[i] > high[i-1] else 'down'
        elif trend == 'up':
            sar[i] = sar[i-1] + af * (ep - sar[i-1])
            if high[i] > ep:
                ep = high[i]
                af = min(af + af_step, af_max)
            if low[i] < sar[i]:
                trend = 'down'
                sar[i] = ep
                af = af_start
                ep = low[i]
        elif trend == 'down':
            sar[i] = sar[i-1] - af * (sar[i-1] - ep)
            if low[i] < ep:
                ep = low[i]
                af = min(af + af_step, af_max)
            if high[i] > sar[i]:
                trend = 'up'
                sar[i] = ep
                af = af_start
                ep = high[i]
    return sar
'''