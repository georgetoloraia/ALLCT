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
        buy_price = await get_current_price(combo_pair)

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

async def main():
    while True:
        try:
            await trade_combo()
        except Exception as e:
            logger.error(f"An error occurred during trading: {e}")
        await asyncio.sleep(60)  # Wait for 1 minute before the next trading cycle

if __name__ == "__main__":
    asyncio.run(main())
