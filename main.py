import telebot
import time
import pandas as pd
import ta
from datetime import datetime, timezone
import threading
import yfinance as yf
import logging
from collections import defaultdict

# ================= CONFIG =================
TELEGRAM_TOKEN = "6152497989:AAFLNR2uAAfakVvO8aBOU__eNjljmbOtzXc"

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Active Chats (jahan bot signals bhejega)
active_chats = set()

# All Major Pairs
ASSETS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X", "USDCHF=X", "NZDUSD=X",
    "EURJPY=X", "GBPJPY=X", "EURGBP=X", "AUDJPY=X", "EURCAD=X", "GBPAUD=X",
    "USDINR=X", "EURINR=X"
]

MIN_CONFIDENCE = 88
SIGNAL_COOLDOWN = 300

signal_history = defaultdict(list)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Currency Names
CURRENCY_NAMES = {
    "EURUSD": "EUR/USD", "GBPUSD": "GBP/USD", "USDJPY": "USD/JPY", "AUDUSD": "AUD/USD",
    "USDCAD": "USD/CAD", "USDCHF": "USD/CHF", "NZDUSD": "NZD/USD", "EURJPY": "EUR/JPY",
    "GBPJPY": "GBP/JPY", "EURGBP": "EUR/GBP", "AUDJPY": "AUD/JPY", "EURCAD": "EUR/CAD",
    "GBPAUD": "GBP/AUD", "USDINR": "USD/INR", "EURINR": "EUR/INR"
}

def get_pair_name(asset):
    key = asset.replace("=X", "")
    return CURRENCY_NAMES.get(key, key)

# ================= DATA & INDICATORS =================
def get_candles(asset, interval="1m", limit=250):
    try:
        df = yf.download(asset, period="4d", interval=interval, progress=False)
        if len(df) < 100:
            return pd.DataFrame()
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        df.rename(columns={'Close': 'close', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Volume': 'volume'}, inplace=True)
        return df.tail(limit)
    except:
        return pd.DataFrame()

def is_good_trading_time():
    hour = datetime.now(timezone.utc).hour
    return 7 <= hour <= 21

def generate_signal(asset):
    try:
        df1 = get_candles(asset, "1m", 280)
        df5 = get_candles(asset, "5m", 120)
        if len(df1) < 150 or len(df5) < 60:
            return None

        for df in [df1, df5]:
            df['rsi'] = ta.rsi(df['close'], length=14)
            df['ema9'] = ta.ema(df['close'], length=9)
            df['ema21'] = ta.ema(df['close'], length=21)
            macd = ta.macd(df['close'])
            df['macd'] = macd['MACD_12_26_9']
            df['macd_signal'] = macd['MACDs_12_26_9']
            bb = ta.bbands(df['close'])
            df['bb_middle'] = bb['BBM_20_2.0']

        l1 = df1.iloc[-1]
        p1 = df1.iloc[-2]
        l5 = df5.iloc[-1]

        if not is_good_trading_time():
            return None

        pair_key = asset.replace("=X", "")
        now_ts = time.time()
        if signal_history[pair_key] and now_ts - signal_history[pair_key][-1] < SIGNAL_COOLDOWN:
            return None

        direction = None
        reasons = []
        confidence = 85

        # Strong Bullish
        if (p1['ema9'] < p1['ema21'] and l1['ema9'] > l1['ema21'] and
            l1['rsi'] < 65 and l1['macd'] > l1['macd_signal'] and
            l1['close'] > l1['bb_middle'] and l5['close'] > l5['ema21']):

            confidence = 88 + int((70 - l1['rsi']) * 0.5)
            direction = "CALL"
            reasons = ["EMA Bull Cross", "MACD Bull", "Above BB", "HTF Uptrend"]

        # Strong Bearish
        elif (p1['ema9'] > p1['ema21'] and l1['ema9'] < l1['ema21'] and
              l1['rsi'] > 35 and l1['macd'] < l1['macd_signal'] and
              l1['close'] < l1['bb_middle'] and l5['close'] < l5['ema21']):

            confidence = 88 + int((l1['rsi'] - 30) * 0.5)
            direction = "PUT"
            reasons = ["EMA Bear Cross", "MACD Bear", "Below BB", "HTF Downtrend"]

        if direction and confidence >= MIN_CONFIDENCE:
            signal_history[pair_key].append(now_ts)
            if len(signal_history[pair_key]) > 10:
                signal_history[pair_key].pop(0)

            utc_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

            return {
                "name": get_pair_name(asset),
                "direction": direction,
                "confidence": min(95, int(confidence)),
                "reason": " | ".join(reasons),
                "timestamp": utc_time
            }
    except:
        pass
    return None

# ================= COMMANDS =================
@bot.message_handler(commands=['start'])
def welcome(message):
    active_chats.add(message.chat.id)
    bot.reply_to(message, "🚀 **Quotex Auto Pro Bot Activated!**\n\n"
                          "✅ Ab main khud best signals analyze karke yahin bhejta rahunga.\n"
                          "⏰ UTC Time (Quotex Server)\n"
                          "Commands: /signals | /future | /status")

@bot.message_handler(commands=['status'])
def status(message):
    active_chats.add(message.chat.id)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    bot.reply_to(message, f"🟢 **Bot Active**\n⏰ Quotex Server Time: **{now}**\n📍 Active in {len(active_chats)} Chat(s)")

@bot.message_handler(commands=['signals'])
def manual_signals(message):
    active_chats.add(message.chat.id)
    bot.reply_to(message, "🔍 Generating Best Signals...")
    for asset in ASSETS:
        signal = generate_signal(asset)
        if signal:
            msg = f"""🔔 **LIVE SIGNAL**

**{signal['name']}**
Direction: **{signal['direction']}**
Confidence: **{signal['confidence']}%**
Reason: {signal['reason']}
Time: {signal['timestamp']} **UTC**"""
            bot.send_message(message.chat.id, msg, parse_mode='Markdown')
        time.sleep(2)

@bot.message_handler(commands=['future'])
def future_signals(message):
    active_chats.add(message.chat.id)
    bot.reply_to(message, "📅 **Next High Probability Signals**")
    found = False
    for asset in ASSETS:
        signal = generate_signal(asset)
        if signal:
            found = True
            msg = f"""⏰ **{signal['name']}** → **{signal['direction']}**
Confidence: **{signal['confidence']}%**
Expected: {signal['timestamp']} UTC
Reason: {signal['reason']}"""
            bot.send_message(message.chat.id, msg, parse_mode='Markdown')
            time.sleep(1.5)
    if not found:
        bot.send_message(message.chat.id, "⏳ Abhi strong signal nahi mila.")

# ================= AUTO SIGNAL THREAD =================
def auto_signal_sender():
    while True:
        try:
            if is_good_trading_time() and active_chats:
                for asset in ASSETS:
                    signal = generate_signal(asset)
                    if signal:
                        msg = f"""🚀 **AUTO SIGNAL**

**{signal['name']}**
Direction: **{signal['direction']}**
Confidence: **{signal['confidence']}%**
Reason: {signal['reason']}
Time: {signal['timestamp']} **UTC** (Quotex Server Time)

⚠️ 0.5% - 1% Risk Only | Trade Smart"""

                        # Sab active chats mein bhejo
                        for chat_id in list(active_chats):
                            try:
                                bot.send_message(chat_id, msg, parse_mode='Markdown')
                            except:
                                active_chats.discard(chat_id)  # Agar chat invalid ho to remove
                        time.sleep(4)
            time.sleep(45)
        except Exception as e:
            logging.error(f"Auto sender error: {e}")
            time.sleep(30)

# ================= START BOT =================
if __name__ == "__main__":
    print("🚀 Quotex Auto Pro Bot Starting...")
    threading.Thread(target=auto_signal_sender, daemon=True).start()
    print("✅ Bot is now live. /start karo group mein!")
    bot.infinity_polling()
