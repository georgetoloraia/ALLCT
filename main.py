import ccxt.async_support as ccxt
# import ccxt
# exchange = ccxt.binance()

import asyncio
import logging
import pandas as pd
from securedFiles import config
# ------
# from src.ema import ema
# from src.wma import wma
# from src.bollinger_bands import bollinger_bands
# from src.vwap import vwap
# from src.avl import avl
# from src.trix import trix
# from src.sar import sar

import talib


# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Initialize Binance exchange connection
exchange = ccxt.binance({
    'apiKey': config.API_KEY,
    'secret': config.SECRET,
    'enableRateLimit': True,
    'options': {'adjustForTimeDifference': True}
})

# Parameters
quote_currency = 'USDT'
initial_investment = 10.0  # USD
trailing_stop_loss_percentage = 10  # 10% trailing stop loss
short_ma_length = 5
long_ma_length = 20
rsi_period = 14  # User's RSI period

# Fetch all tradeable pairs using the correct asynchronous call
async def get_tradeable_pairs(quote_currency):
    try:
        if asyncio.iscoroutinefunction(exchange.load_markets):
            await exchange.load_markets()
        else:
            exchange.load_markets()  # Call without await if it's not awaitable
        return [symbol for symbol in exchange.symbols if quote_currency in symbol.split('/')]
    except Exception as e:
        logger.error(f"Error loading markets: {e}")
        return []


# Ensure that the 'close' method is correctly implemented
async def close_exchange():
    print("Exchange type:", type(exchange))
    print("Is 'load_markets' awaitable?", asyncio.iscoroutinefunction(exchange.load_markets))
    if hasattr(exchange, 'close'):
        await exchange.close()
        

    else:
        logger.info("No need to close the exchange connection explicitly.")

def preprocess_data(df):
    # Ensure all required columns are present and of the correct type
    required_columns = ['open', 'high', 'low', 'close', 'volume']
    if not all(col in df.columns for col in required_columns):
        raise ValueError("DataFrame must contain open, high, low, close, and volume columns")

    df = df.ffill().bfill()

    return df




async def fetch_historical_prices(pair, limit=100):
    try:
        ohlcv = await exchange.fetch_ohlcv(pair, timeframe='1m', limit=limit)
        if ohlcv is None or len(ohlcv) == 0:
            logger.info(f"No data returned for {pair}.")
            return pd.DataFrame()

        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)

        df = preprocess_data(df)

        df['ema'] = talib.EMA(df['close'], timeperiod=14)
        df['wma'] = talib.WMA(df['close'], timeperiod=14)
        df['upper_band'], df['middle_band'], df['lower_band'] = talib.BBANDS(df['close'], timeperiod=20, nbdevup=2, nbdevdn=2)
        # df['vwap'] = talib.vwap(df['close'], df['volume'])  # No direct VWAP in TA-Lib
        df['trix'] = talib.TRIX(df['close'], timeperiod=15)


        # df['ema'] = ema(df['close'], 14)
        
        # df['wma'] = wma(df['close'], 14)
        
        # df['upper_band'], df['lower_band'] = bollinger_bands(df['close'], 20, 2)
        
        # df['vwap'] = vwap(df['close'], df['volume'])
        # df['avl'] = avl(df['close'], df['volume'])
        # df['trix'] = trix(df['close'], 15)
        

        return df
    except Exception as e:
        logger.error(f"Error fetching historical prices for {pair}: {e}")
        return pd.DataFrame()




# Evaluate Trading Signal
def evaluate_trading_signals(df):
    if df.empty:
        logger.info("DataFrame is empty.")
        return False, None

    # Check for any NaN values in the required columns for trading decisions
    required_columns = ['ema', 'wma', 'upper_band', 'lower_band', 'avl', 'trix'] #, 'sar'
    # if df[required_columns].isnull().any().any():
    #     logger.info("DataFrame contains NaN values in required columns.")
    #     return False, None
    
    latest = df.iloc[-1]

    buy_conditions = [
        latest['close'] > latest['ema'],
        latest['close'] > latest['wma'],
        # latest['close'] > latest['vwap'],
        latest['trix'] > 0,
        # latest['close'] > latest['sar'],
        latest['close'] < latest['lower_band']
    ]
    
    sell_conditions = [
        latest['close'] < latest['ema'],
        latest['close'] < latest['wma'],
        # latest['close'] < latest['vwap'],
        latest['trix'] < 0,
        # latest['close'] < latest['sar'],
        latest['close'] > latest['upper_band']
    ]

    if all(buy_conditions):
        logger.info(f"Buy signal conditions met: {dict(zip(required_columns + ['close < Lower Band'], buy_conditions))}")
        return True, 'buy'
    elif all(sell_conditions):
        logger.info(f"Sell signal conditions met: {dict(zip(required_columns + ['close > Upper Band'], sell_conditions))}")
        return True, 'sell'
    return False, None


# Get balance
async def get_balance(currency):
    try:
        balance = await exchange.fetch_balance()
        available_balance = balance['free'][currency]
        logger.info(f"Available balance for {currency}: {available_balance}")
        return available_balance
    except Exception as e:
        logger.error(f"Error fetching balance for {currency}: {e}")
        return 0

# Get current price
async def get_current_price(pair):
    try:
        ticker = await exchange.fetch_ticker(pair)
        current_price = ticker['last']
        logger.info(f"Current market price for {pair}: {current_price}")
        return current_price
    except Exception as e:
        logger.error(f"Error fetching current price for {pair}: {e}")
        return None

# Place Market Ordder
async def place_market_order(pair, side, amount):
    if amount <= 0:
        logger.error(f"Invalid amount for {side} order: {amount}")
        return None
    try:
        if side == 'buy':
            order = await exchange.create_market_buy_order(pair, amount)
        elif side == 'sell':
            order = await exchange.create_market_sell_order(pair, amount)
        logger.info(f"Market {side} order placed for {pair}: {amount} units at market price.")
        return order
    except Exception as e:
        logger.error(f"An error occurred placing a {side} order for {pair}: {e}")
        return None


# Main trading logic
async def trade():
    pairs = await get_tradeable_pairs('USDT')
    for pair in pairs:
        try:
            data = await fetch_historical_prices(pair)
            # print("es aris \n-----\n", data)
            if not data.empty:
                signal, action = evaluate_trading_signals(data)
                if signal:
                    logger.info(f"Signal detected: {action.upper()} for {pair}")
                    usdt_balance = await get_balance('USDT')
                    if usdt_balance < initial_investment:
                        logger.warning(f"Insufficient USDT to trade. Available: {usdt_balance}, Required: {initial_investment}")
                        continue

                    current_price = await get_current_price(pair)
                    if current_price is None:
                        continue

                    amount = initial_investment / current_price
                    if action == 'buy':
                        order_result = await place_market_order(pair, 'buy', amount)
                        if order_result:
                            logger.info(f"Buy order placed for {amount} of {pair} at {current_price}")
                    elif action == 'sell':
                        asset = pair.split('/')[0]
                        asset_balance = await get_balance(asset)
                        if asset_balance < amount:
                            logger.warning(f"Insufficient {asset} balance. Available: {asset_balance}, Required: {amount}")
                            continue
                        order_result = await place_market_order(pair, 'sell', amount)
                        if order_result:
                            logger.info(f"Sell order placed for {amount} of {pair} at {current_price}")
        except Exception as e:
            logger.error(f"An error occurred while processing {pair}: {str(e)}")

async def main():
    try:
        await trade()
    except Exception as e:
        logger.error(f"An error occurred during trading: {e}")
    finally:
        # Call the close_exchange function correctly
        await close_exchange()
        logger.info("Exchange connection closed.")

if __name__ == "__main__":
    asyncio.run(main())

