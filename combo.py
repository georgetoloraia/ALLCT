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
combo_pair = 'COMBO/USDT'  # Focus on COMBO coin
commission_rate = 0.001  # 0.1% commission

# Fetch historical data and calculate technical indicators
async def fetch_historical_prices(pair, limit=100):
    try:
        ohlcv = await exchange.fetch_ohlcv(pair, timeframe='1m', limit=limit)
        if ohlcv is None or len(ohlcv) == 0:
            logger.info(f"No data returned for {pair}.")
            return pd.DataFrame()

        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)

        df['rsi'] = talib.RSI(df['close'], timeperiod=14)
        df['macd'], df['macd_signal'], _ = talib.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
        df['upper_band'], df['middle_band'], df['lower_band'] = talib.BBANDS(df['close'], timeperiod=20, nbdevup=2, nbdevdn=2)

        return df
    except Exception as e:
        logger.error(f"Error fetching historical prices for {pair}: {e}")
        return pd.DataFrame()

# Calculate net profit after commission
def calculate_net_profit(buy_price, sell_price):
    gross_profit = sell_price / buy_price
    net_profit = gross_profit * (1 - 2 * commission_rate)  # accounting for buy and sell commission
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

async def get_balance(currency):
    try:
        balance = await exchange.fetch_balance()
        available_balance = balance['free'][currency]
        logger.info(f"Available balance for {currency}: {available_balance}")
        return available_balance
    except Exception as e:
        logger.error(f"Error fetching balance for {currency}: {e}")
        return 0

async def get_current_price(pair):
    try:
        ticker = await exchange.fetch_ticker(pair)
        current_price = ticker['last']
        logger.info(f"Current market price for {pair}: {current_price}")
        return current_price
    except Exception as e:
        logger.error(f"Error fetching current price for {pair}: {e}")
        return None

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

# Evaluate trading signals based on TA-Lib indicators
def evaluate_trading_signals(df):
    if df.empty:
        logger.info("DataFrame is empty.")
        return False, None

    latest = df.iloc[-1]
    
    buy_conditions = [
        latest['rsi'] < 30,  # RSI indicating oversold
        latest['macd'] > latest['macd_signal'],  # MACD crossover
        latest['close'] < latest['lower_band']  # Price below lower Bollinger Band
    ]
    
    sell_conditions = [
        latest['rsi'] > 70,  # RSI indicating overbought
        latest['macd'] < latest['macd_signal'],  # MACD crossover
        latest['close'] > latest['upper_band']  # Price above upper Bollinger Band
    ]

    if all(buy_conditions):
        logger.info(f"Buy signal conditions met: {dict(zip(['rsi', 'macd', 'close < lower_band'], buy_conditions))}")
        return True, 'buy'
    elif all(sell_conditions):
        logger.info(f"Sell signal conditions met: {dict(zip(['rsi', 'macd', 'close > upper_band'], sell_conditions))}")
        return True, 'sell'
    return False, None

async def trade_combo():
    usdt_balance = await get_balance('USDT')
    combo_balance = await get_balance('COMBO')

    if usdt_balance > 0:
        # Buy COMBO with all available USDT
        current_price = await get_current_price(combo_pair)
        amount = usdt_balance / current_price
        order_result = await place_market_order(combo_pair, 'buy', amount)
        if order_result:
            logger.info(f"Buy order placed for {amount} of {combo_pair} at {current_price}")
            buy_price = current_price

            # Monitor for profit opportunities
            while True:
                await asyncio.sleep(60)  # Check every minute
                current_price = await get_current_price(combo_pair)
                if current_price:
                    net_profit = calculate_net_profit(buy_price, current_price)
                    if net_profit > 1:  # Profit condition (greater than initial investment)
                        logger.info(f"Profit opportunity detected for {combo_pair}. Converting to USDT.")
                        await convert_to_usdt(combo_pair)
                        break

    elif combo_balance > 0:
        data = await fetch_historical_prices(combo_pair)
        while True:
            await asyncio.sleep(60)  # Check every minute
            signal, action = evaluate_trading_signals(data)
            if action == 'sell':
                current_price = await get_current_price(combo_pair)
                net_profit = calculate_net_profit(buy_price, current_price)
                if net_profit > 1:  # Profit condition (greater than initial investment)
                    logger.info(f"Profit opportunity detected for {combo_pair}. Converting to USDT.")
                    await convert_to_usdt(combo_pair)
                    break

async def main():
    while True:
        try:
            await trade_combo()
        except Exception as e:
            logger.error(f"An error occurred during trading: {e}")
        await asyncio.sleep(60)  # Wait for 1 minute before the next trading cycle

if __name__ == "__main__":
    asyncio.run(main())
