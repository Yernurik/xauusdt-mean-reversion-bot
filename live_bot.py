import os
import time
import pandas as pd
import numpy as np
import requests
from pybit.unified_trading import HTTP


BYBIT_API_KEY = None
BYBIT_API_SECRET = None
TELEGRAM_TOKEN = None
TELEGRAM_CHAT_ID = None

try:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    env_file = os.path.join(base_dir, '.env')

    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, val = line.split('=', 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")

                if key == 'BYBIT_API_KEY':
                    BYBIT_API_KEY = val
                elif key == 'BYBIT_API_SECRET':
                    BYBIT_API_SECRET = val
                elif key == 'TELEGRAM_TOKEN':
                    TELEGRAM_TOKEN = val
                elif key == 'TELEGRAM_CHANNEL_ID':
                    TELEGRAM_CHAT_ID = val
except Exception as e:
    print(f"❌ Error reading .env file manually in live bot: {e}")


SYMBOL = "XAUUSDT"
CATEGORY = "linear"
TIMEFRAME = "15"
LIMIT = 100

MA_WINDOW = 50
Z_ENTRY = 3.0
Z_EXIT = 0.2
ATR_WINDOW = 14
ATR_MULTIPLIER = 1.5
VOLUME = 0.01  # Minimum contract size for Gold on Bybit


session = HTTP(testnet=False, api_key=BYBIT_API_KEY, api_secret=BYBIT_API_SECRET)
current_position = None
entry_price = 0.0
target_price = 0.0
breakeven_active = False


def send_telegram_message(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠ Live Bot: Telegram credentials not found in .env!")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        response = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=10)
        if response.status_code != 200:
            print(f"⚠ Live Bot TG API Error: {response.status_code} -> {response.text}")
    except Exception as e:
        print(f"❌ Live Bot: Critical TG network error: {e}")

def get_market_data():
    try:
        klines = session.get_kline(category=CATEGORY, symbol=SYMBOL, interval=TIMEFRAME, limit=LIMIT)
        df = pd.DataFrame(klines['result']['list'], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
        df = df.iloc[::-1].reset_index(drop=True)

        df['close'] = df['close'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)

        df['ma'] = df['close'].rolling(window=MA_WINDOW).mean()
        df['std'] = df['close'].rolling(window=MA_WINDOW).std()
        df['z_score'] = (df['close'] - df['ma']) / df['std']

        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['close'].shift(1))
        df['tr3'] = abs(df['low'] - df['close'].shift(1))
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        df['atr'] = df['tr'].rolling(window=ATR_WINDOW).mean()

        last_row = df.iloc[-1]
        return last_row['close'], last_row['z_score'], last_row['ma'], last_row['atr']
    except Exception as e:
        print(f"Error fetching market data: {e}")
        return None, None, None, None

def check_signals(current_price, z_score, current_ma, current_atr):
    global current_position, entry_price, target_price, breakeven_active

    sl_distance = current_atr * ATR_MULTIPLIER
    print(f"📊 Price: {current_price} | Z: {z_score:.2f} | ATR: {current_atr:.2f} | Pos: {current_position} | BE: {breakeven_active}")

    # ENTRY LOGIC & ORDER EXECUTION
    if current_position is None:
        if z_score >= Z_ENTRY:
            try:
                # Execution of real Market Short Order
                session.place_order(category=CATEGORY, symbol=SYMBOL, side="Sell", orderType="Market", qty=str(VOLUME))
                current_position = "Sell"
                entry_price = current_price
                target_price = current_ma
                breakeven_active = False
                send_telegram_message(f"🚨 REAL SHORT OPENED!\nPrice: {entry_price}\nVolume: {VOLUME}\nStop Loss: {entry_price + sl_distance:.2f}")
            except Exception as e:
                print(f"❌ Error opening Short position on exchange: {e}")

        elif z_score <= -Z_ENTRY:
            try:
                # Execution of real Market Long Order
                session.place_order(category=CATEGORY, symbol=SYMBOL, side="Buy", orderType="Market", qty=str(VOLUME))
                current_position = "Buy"
                entry_price = current_price
                target_price = current_ma
                breakeven_active = False
                send_telegram_message(f"🚨 REAL LONG OPENED!\nPrice: {entry_price}\nVolume: {VOLUME}\nStop Loss: {entry_price - sl_distance:.2f}")
            except Exception as e:
                print(f"❌ Error opening Long position on exchange: {e}")

    # SHORT POSITION MANAGEMENT
    elif current_position == "Sell":
        stop_loss_level = entry_price if breakeven_active else (entry_price + sl_distance)
        total_path = abs(target_price - entry_price)
        current_progress = abs(current_price - entry_price)

        if not breakeven_active and total_path > 0 and (current_progress / total_path) >= 0.50:
            if current_price < entry_price:
                breakeven_active = True
                send_telegram_message(f"🔒 BE (Breakeven) Activated for Short at {entry_price}")

        # Exit via Take Profit (Closing Short with a Market Buy)
        if abs(z_score) <= Z_EXIT:
            try:
                session.place_order(category=CATEGORY, symbol=SYMBOL, side="Buy", orderType="Market", qty=str(VOLUME))
                current_position = None
                send_telegram_message(f"✅ REAL TAKE PROFIT (Short closed) at {current_price}")
            except Exception as e: 
                print(f"Error executing Take Profit: {e}")

        # Exit via Stop Loss / Breakeven
        elif current_price >= stop_loss_level:
            try:
                session.place_order(category=CATEGORY, symbol=SYMBOL, side="Buy", orderType="Market", qty=str(VOLUME))
                current_position = None
                send_telegram_message(f"❌ REAL STOP LOSS/BE (Short closed) at {current_price}")
            except Exception as e: 
                print(f"Error executing Stop Loss: {e}")

    # LONG POSITION MANAGEMENT
    elif current_position == "Buy":
        stop_loss_level = entry_price if breakeven_active else (entry_price - sl_distance)
        total_path = abs(target_price - entry_price)
        current_progress = abs(current_price - entry_price)

        if not breakeven_active and total_path > 0 and (current_progress / total_path) >= 0.50:
            if current_price > entry_price:
                breakeven_active = True
                send_telegram_message(f"🔒 BE (Breakeven) Activated for Long at {entry_price}")

        # Exit via Take Profit (Closing Long with a Market Sell)
        if abs(z_score) <= Z_EXIT:
            try:
                session.place_order(category=CATEGORY, symbol=SYMBOL, side="Sell", orderType="Market", qty=str(VOLUME))
                current_position = None
                send_telegram_message(f"✅ REAL TAKE PROFIT (Long closed) at {current_price}")
            except Exception as e: 
                print(f"Error executing Take Profit: {e}")

        # Exit via Stop Loss / Breakeven
        elif current_price <= stop_loss_level:
            try:
                session.place_order(category=CATEGORY, symbol=SYMBOL, side="Sell", orderType="Market", qty=str(VOLUME))
                current_position = None
                send_telegram_message(f"❌ REAL STOP LOSS/BE (Long closed) at {current_price}")
            except Exception as e: 
                print(f"Error executing Stop Loss: {e}")


print("🚀 REAL Quant Bot is running with LIVE trading...")
while True:
    price, z, ma, atr = get_market_data()
    if price is not None and z is not None:
        check_signals(price, z, ma, atr)
    time.sleep(60)