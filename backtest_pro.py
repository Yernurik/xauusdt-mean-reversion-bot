import time
import pandas as pd
import numpy as np
from pybit.unified_trading import HTTP

# --- SETTINGS ---
SYMBOL = "XAUUSDT"
CATEGORY = "linear"
TIMEFRAME = "15"
NEEDED_CANDLES = 3000  

# Strategy Parameters
MA_WINDOW = 50
Z_ENTRY = 3.0
Z_EXIT = 0.2
ATR_WINDOW = 14
ATR_MULTIPLIER = 1.5

# TREND FILTER
TREND_WINDOW = 200  # Added EMA 200 to identify global trend direction

session = HTTP(testnet=False, domain="bytick")

print(f"📥 Starting historical data fetch for {SYMBOL}...")

full_list = []
current_end = None

for block in range(3):
    try:
        if current_end is None:
            klines = session.get_kline(category=CATEGORY, symbol=SYMBOL, interval=TIMEFRAME, limit=1000)
        else:
            klines = session.get_kline(category=CATEGORY, symbol=SYMBOL, interval=TIMEFRAME, limit=1000, end=current_end)
            
        data = klines['result']['list']
        if not data or len(data) == 0: 
            break
        full_list.extend(data)
        current_end = int(data[-1][0]) - 1
        print(f"   Downloaded block {block + 1}/3...")
        time.sleep(0.3)
    except Exception as e:
        print(f"Error fetching data: {e}")
        break

df = pd.DataFrame(full_list, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
df = df.drop_duplicates(subset=['timestamp']).sort_values(by='timestamp').reset_index(drop=True)

df['close'] = df['close'].astype(float)
df['high'] = df['high'].astype(float)
df['low'] = df['low'].astype(float)

print(f"✅ Successfully collected {len(df)} candles!")

# Indicator Calculations
df['ma'] = df['close'].rolling(window=MA_WINDOW).mean()
df['std'] = df['close'].rolling(window=MA_WINDOW).std()
df['z_score'] = (df['close'] - df['ma']) / df['std']

# Global Trend via EMA 200
df['trend_ema'] = df['close'].ewm(span=TREND_WINDOW, adjust=False).mean()

df['tr1'] = df['high'] - df['low']
df['tr2'] = abs(df['high'] - df['close'].shift(1))
df['tr3'] = abs(df['low'] - df['close'].shift(1))
df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
df['atr'] = df['tr'].rolling(window=ATR_WINDOW).mean()
df = df.dropna().reset_index(drop=True)

# Simulation Engine
position = None
entry_price = 0.0
stop_loss = 0.0
target_price = 0.0
breakeven_active = False
trades_log = []

for i in range(len(df)):
    row = df.iloc[i]
    current_price = row['close']
    z = row['z_score']
    atr = row['atr']
    ema = row['trend_ema']
    
    if position is None:
        # SHORT Entry Rules: Z >= 3.0 AND Price < EMA 200 (Downtrend)
        if z >= Z_ENTRY and current_price < ema:
            position = "Sell"
            entry_price = current_price
            stop_loss = current_price + (atr * ATR_MULTIPLIER)
            target_price = row['ma']
            breakeven_active = False
            
        # LONG Entry Rules: Z <= -3.0 AND Price > EMA 200 (Uptrend)
        elif z <= -Z_ENTRY and current_price > ema:
            position = "Buy"
            entry_price = current_price
            stop_loss = current_price - (atr * ATR_MULTIPLIER)
            target_price = row['ma']
            breakeven_active = False
    else:
        total_path = abs(target_price - entry_price)
        current_progress = abs(current_price - entry_price)
        
        if not breakeven_active and total_path > 0 and (current_progress / total_path) >= 0.50:
            breakeven_active = True
            stop_loss = entry_price

        if position == "Sell":
            if row['high'] >= stop_loss:
                pnl = entry_price - stop_loss
                trades_log.append({"result": "Profit" if pnl > 0 else ("Loss" if pnl < 0 else "Flat"), "pnl": pnl})
                position = None
            elif abs(z) <= Z_EXIT:
                pnl = entry_price - current_price
                trades_log.append({"result": "Profit" if pnl > 0 else "Loss", "pnl": pnl})
                position = None
                
        elif position == "Buy":
            if row['low'] <= stop_loss:
                pnl = stop_loss - entry_price
                trades_log.append({"result": "Profit" if pnl > 0 else ("Loss" if pnl < 0 else "Flat"), "pnl": pnl})
                position = None
            elif abs(z) <= Z_EXIT:
                pnl = current_price - entry_price
                trades_log.append({"result": "Profit" if pnl > 0 else "Loss", "pnl": pnl})
                position = None

print("\n" + "="*40)
print(f"📊 GOLD BACKTEST WITH TREND FILTER (EMA {TREND_WINDOW}):")
print("="*40)
t_df = pd.DataFrame(trades_log)

if len(t_df) == 0:
    print("No trades found matching the trend filter criteria.")
else:
    total_trades = len(t_df)
    wins = len(t_df[t_df['result'] == "Profit"])
    losses = len(t_df[t_df['result'] == "Loss"])
    flats = len(t_df[t_df['result'] == "Flat"])
    total_pnl = t_df['pnl'].sum()
    
    avg_win = t_df[t_df['pnl'] > 0]['pnl'].mean() if wins > 0 else 0
    avg_loss = t_df[t_df['pnl'] < 0]['pnl'].mean() if losses > 0 else 0
    profit_factor = abs(avg_win / avg_loss) if losses > 0 else float('inf')

    print(f"Total Trades Executed: {total_trades}")
    print(f"✅ Wins: {wins} | ❌ Losses: {losses} | 🛡️ Breakeven (Flat): {flats}")
    print(f"🔥 Win Rate: {(wins / total_trades) * 100:.2f}%")
    print(f"💵 Total PnL in points (per 1 lot): {total_pnl:.2f} $")
    print(f"⚙️ Multi-candle Profit Factor: {profit_factor:.2f}")
    print("="*40)