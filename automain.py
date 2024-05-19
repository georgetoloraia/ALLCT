import datetime
import ccxt.async_support as ccxt
import asyncio
import logging
import pandas as pd
from securedFiles import config
import talib


logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Initialize Binance exchange connection
exchange = ccxt.binance({
    'apiKey': config.API_KEY,
    'secret': config.SECRET,
    'enableRateLimit': True,
    'options': {'adjustForTimeDifference': True}
})


profit_target = 1.10  # 10% profit
quote_currency = 'USDT'
initial_investment = 10.0  # USD
trailing_stop_loss_percentage = 10  # 10% trailing stop loss
stop_loss_threshold = 0.90  # 10% drop
short_ma_length = 5
long_ma_length = 20
rsi_period = 14  # User's RSI period
commission_rate = 0.001  # 0.1%

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



def evaluate_trading_signals(df):
    if df.empty:
        logger.info("DataFrame is empty.")
        return False, None

    latest = df.iloc[-1]

    # Define buy and sell conditions using additional indicators
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
        latest['close'] < latest['ema'],  # Price below EMA
        latest['close'] < latest['wma'],  # Price below WMA
        latest['trix'] < 0,  # TRIX negative
        latest['close'] > latest['upper_band'],  # Price above upper Bollinger Band
        latest['rsi'] > 70,  # RSI indicating overbought
        latest['macd'] < latest['macd_signal'],  # MACD below Signal Line
        latest['cci'] > 100,  # CCI indicating overbought
        latest['slowk'] > 80 and latest['slowd'] > 80  # Stochastic Oscillator indicating overbought
    ]

    if all(buy_conditions):
        logger.info(f"Buy signal conditions met: {dict(zip(['ema', 'wma', 'trix', 'close < Lower Band', 'rsi', 'macd', 'cci', 'stoch'], buy_conditions))}")
        return True, 'buy'
    elif all(sell_conditions):
        logger.info(f"Sell signal conditions met: {dict(zip(['ema', 'wma', 'trix', 'close > Upper Band', 'rsi', 'macd', 'cci', 'stoch'], sell_conditions))}")
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

# Place Market Order
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



# Get the ATR value
def get_atr(df):
    return talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)

# Calculate net profit after commission
def calculate_net_profit(buy_price, sell_price):
    gross_profit = sell_price / buy_price
    net_profit = gross_profit * (1 - 2 * commission_rate)  # accounting for buy and sell commission
    return net_profit

async def convert_to_usdt(pair, force=False):
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

async def trade():
    pairs = await get_tradeable_pairs('USDT')
    for pair in pairs:
        try:
            data = await fetch_historical_prices(pair)
            if not data.empty:
                signal, action = evaluate_trading_signals(data)
                atr = get_atr(data)
                latest = data.iloc[-1]
                current_price = latest['close']
                usdt_balance = await get_balance('USDT')

                if signal:
                    logger.info(f"Signal detected: {action.upper()} for {pair}")
                    if usdt_balance < initial_investment:
                        logger.warning(f"Insufficient USDT to trade. Available: {usdt_balance}, Required: {initial_investment}")
                        continue

                    amount = initial_investment / current_price
                    if action == 'buy':
                        order_result = await place_market_order(pair, 'buy', amount)
                        if order_result:
                            logger.info(f"Buy order placed for {amount} of {pair} at {current_price}")
                            buy_price = current_price

                            # Monitor for profit target and high volatility
                            while True:
                                await asyncio.sleep(60)  # Check every minute
                                current_price = await get_current_price(pair)
                                if current_price:
                                    net_profit = calculate_net_profit(buy_price, current_price)
                                    if net_profit >= profit_target:
                                        logger.info(f"Profit target reached for {pair}. Converting to USDT.")
                                        await convert_to_usdt(pair)
                                        break
                                    if atr.iloc[-1] > atr.mean():
                                        logger.info(f"High volatility detected for {pair}. Converting to USDT.")
                                        await convert_to_usdt(pair)
                                        break
                    elif action == 'sell':
                        asset = pair.split('/')[0]
                        asset_balance = await get_balance(asset)
                        if asset_balance < amount:
                            logger.warning(f"Insufficient {asset} balance. Available: {asset_balance}, Required: {amount}")
                            continue
                        order_result = await place_market_order(pair, 'sell', amount)
                        if order_result:
                            logger.info(f"Sell order placed for {amount} of {pair} at {current_price}")
                            await convert_to_usdt(pair)

                # Stop-loss trigger
                if action == 'buy' and current_price < latest['close'] * stop_loss_threshold:
                    await convert_to_usdt(pair, force=True)
        except Exception as e:
            logger.error(f"An error occurred while processing {pair}: {str(e)}")

async def main():
    while True:
        try:
            await trade()
        except Exception as e:
            logger.error(f"An error occurred during trading: {e}")
        await asyncio.sleep(60)  # Wait for 1 minute before the next trading cycle

if __name__ == "__main__":
    asyncio.run(main())
