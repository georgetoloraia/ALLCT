import datetime
import ccxt.async_support as ccxt
import asyncio
import logging
import pandas as pd
from securedFiles import config
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
rsi_period = 14  # User's RSI period
commission_rate = 0.001  # 0.1%

# New coins monitoring
initial_pairs = set()
initial_prices = {}

async def fetch_initial_pairs(quote_currency):
    global initial_pairs
    try:
        await exchange.load_markets()
        initial_pairs = set(exchange.symbols)
        logger.info("Fetched initial trading pairs.")
        return [symbol for symbol in exchange.symbols if quote_currency in symbol.split('/')]
    except Exception as e:
        logger.error(f"Error fetching initial trading pairs: {e}")
        return []

async def detect_newly_listed_coins():
    global initial_pairs
    global initial_prices
    try:
        await exchange.load_markets()
        current_pairs = set(exchange.symbols)
        newly_listed_coins = current_pairs - initial_pairs
        if newly_listed_coins:
            logger.info(f"Newly listed coins detected: {newly_listed_coins}")
            for pair in newly_listed_coins:
                initial_price = await get_current_price(pair)
                if initial_price:
                    initial_prices[pair] = initial_price
                    logger.info(f"Initial price for {pair}: {initial_price}")
            initial_pairs = current_pairs  # Update initial pairs
        return newly_listed_coins
    except Exception as e:
        logger.error(f"Error detecting newly listed coins: {e}")
        return set()

async def get_current_price(pair):
    try:
        ticker = await exchange.fetch_ticker(pair)
        current_price = ticker['last']
        logger.info(f"Current market price for {pair}: {current_price}")
        return current_price
    except Exception as e:
        logger.error(f"Error fetching current price for {pair}: {e}")
        return None

async def get_balance(currency):
    try:
        balance = await exchange.fetch_balance()
        available_balance = balance['free'][currency]
        logger.info(f"Available balance for {currency}: {available_balance}")
        return available_balance
    except Exception as e:
        logger.error(f"Error fetching balance for {currency}: {e}")
        return 0

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

def calculate_net_profit(buy_price, sell_price):
    gross_profit = sell_price / buy_price
    net_profit = gross_profit * (1 - 2 * commission_rate)
    return net_profit

async def convert_to_usdt(pair):
    try:
        asset = pair.split('/')[0]
        asset_balance = await get_balance(asset)
        if asset_balance > 0:
            order_result = await place_market_order(pair, 'sell', asset_balance)
            if order_result:
                logger.info(f"Converted {asset_balance} of {asset} to USDT")
                return order_result
        else:
            logger.info(f"No {asset} balance to convert to USDT")
    except Exception as e:
        logger.error(f"An error occurred converting {pair} to USDT: {e}")
    return None

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
        df['trix'] = talib.TRIX(df['close'], timeperiod=15)
        df['rsi'] = talib.RSI(df['close'], timeperiod=14)
        df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
        df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
        df['slowk'], df['slowd'] = talib.STOCH(df['high'], df['low'], df['close'], fastk_period=14, slowk_period=3, slowk_matype=0, slowd_period=3, slowd_matype=0)
        df['cci'] = talib.CCI(df['high'], df['low'], df['close'], timeperiod=14)
        df['obv'] = talib.OBV(df['close'], df['volume'])

        return df
    except Exception as e:
        logger.error(f"Error fetching historical prices for {pair}: {e}")
        return pd.DataFrame()

def preprocess_data(df):
    required_columns = ['open', 'high', 'low', 'close', 'volume']
    if not all(col in df.columns for col in required_columns):
        raise ValueError("DataFrame must contain open, high, low, close, and volume columns")

    df = df.ffill().bfill()
    return df

def evaluate_trading_signals(df):
    if df.empty:
        logger.info("DataFrame is empty.")
        return False, None

    latest = df.iloc[-1]

    buy_conditions = [
        latest['close'] > latest['ema'],
        latest['close'] > latest['wma'],
        latest['trix'] > 0,
        latest['close'] < latest['lower_band'],
        latest['rsi'] < 30,
        latest['macd'] > latest['macd_signal'],
        latest['cci'] < -100,
        latest['slowk'] < 20 and latest['slowd'] < 20
    ]
    
    sell_conditions = [
        latest['close'] < latest['ema'],
        latest['close'] < latest['wma'],
        latest['trix'] < 0,
        latest['close'] > latest['upper_band'],
        latest['rsi'] > 70,
        latest['macd'] < latest['macd_signal'],
        latest['cci'] > 100,
        latest['slowk'] > 80 and latest['slowd'] > 80
    ]

    if all(buy_conditions):
        logger.info(f"Buy signal conditions met: {dict(zip(['ema', 'wma', 'trix', 'close < Lower Band', 'rsi', 'macd', 'cci', 'stoch'], buy_conditions))}")
        return True, 'buy'
    elif all(sell_conditions):
        logger.info(f"Sell signal conditions met: {dict(zip(['ema', 'wma', 'trix', 'close > Upper Band', 'rsi', 'macd', 'cci', 'stoch'], sell_conditions))}")
        return True, 'sell'
    return False, None

async def trade():
    pairs = await fetch_initial_pairs(quote_currency)
    initial_usdt_balance = await get_balance('USDT')
    logger.info(f"Initial USDT balance: {initial_usdt_balance}")

    while True:
        try:
            newly_listed_coins = await detect_newly_listed_coins()
            for pair in newly_listed_coins:
                current_price = await get_current_price(pair)
                if current_price:
                    initial_price = initial_prices.get(pair)
                    if initial_price:
                        price_increase = (current_price / initial_price - 1) * 100
                        if price_increase >= 1000:
                            logger.info(f"Price increase detected for {pair}: {price_increase:.2f}% since initial price.")
                            asset_balance = await get_balance(pair.split('/')[0])
                            await place_market_order(pair, 'sell', asset_balance)
                            await convert_to_usdt(pair)
                            continue

                    historical_data = await fetch_historical_prices(pair)
                    signal, action = evaluate_trading_signals(historical_data)
                    if signal:
                        amount_to_invest = initial_usdt_balance * (1 - commission_rate)
                        order_result = await place_market_order(pair, action, amount_to_invest)
                        if order_result:
                            logger.info(f"Order result: {order_result}")
                            await asyncio.sleep(60)
                            await convert_to_usdt(pair)
        except Exception as e:
            logger.error(f"Error in main trading loop: {e}")
        await asyncio.sleep(60)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(trade())
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(exchange.close())
        loop.close()
