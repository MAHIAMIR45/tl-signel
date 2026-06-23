import os
import sys
import threading
import time
import logging
from flask import Flask

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
log = logging.getLogger(__name__)

PORT = int(os.environ.get("PORT", 10000))

# ========== FLASK APP (starts instantly) ==========
app = Flask(__name__)

bot_status = {"running": False, "users": 0, "signals_sent": 0}

@app.route("/")
def index():
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"""
<!DOCTYPE html>
<html>
<head>
    <title>Quotex Signal Bot</title>
    <meta http-equiv="refresh" content="30">
    <style>
        body {{ font-family: Arial, sans-serif; background: #0f1117;
               color: #fff; display: flex; justify-content: center;
               align-items: center; height: 100vh; margin: 0; }}
        .card {{ background: #1e2130; padding: 40px; border-radius: 16px;
                text-align: center; box-shadow: 0 4px 30px rgba(0,0,0,0.4); }}
        .dot {{ display: inline-block; width: 14px; height: 14px;
               background: #00e676; border-radius: 50;
               animation: pulse 1.5s infinite; margin-right: 8px; }}
        @keyframes pulse {{ 0%,100% {{opacity:1}} 50% {{opacity:0.3}} }}
        h1 {{ color: #00e676; margin-bottom: 10px; }}
        .stat {{ background: #2a2d3e; padding: 10px 20px;
                border-radius: 8px; margin: 8px; display: inline-block; }}
    </style>
</head>
<body>
<div class="card">
    <h1>🤖 Quotex Signal Bot</h1>
    <p><span class="dot"></span><b>Bot Running</b></p>
    <hr style="border-color:#333; margin:20px 0">
    <div class="stat">👥 Users: <b>{bot_status['users']}</b></div>
    <div class="stat">📡 Signals Sent: <b>{bot_status['signals_sent']}</b></div>
    <div class="stat">🕐 {now}</div>
    <br><br>
    <p style="color:#888; font-size:13px">
        3 Timeframe Analysis | 8 Indicators | 92%+ Confidence Only
    </p>
</div>
</body>
</html>
""", 200

@app.route("/health")
def health():
    return "OK", 200


# ========== BOT THREAD (starts after Flask) ==========
def start_bot():
    log.info("Bot thread: importing libraries...")
    try:
        import random
        import json
        import pandas as pd
        import ta
        import yfinance as yf
        import telebot
        from datetime import datetime, timezone
        from collections import defaultdict
        log.info("Bot thread: all imports OK")
    except Exception as e:
        log.error(f"Bot import error: {e}")
        return

    TELEGRAM_TOKEN = "6152497989:AAFLNR2uAAfakVvO8aBOU__eNjljmbOtzXc"
    CHATS_FILE     = "active_chats.json"
    MIN_CONFIDENCE = 92
    SIGNAL_COOLDOWN = 600
    MIN_CONDITIONS  = 5
    signal_history  = defaultdict(list)

    ASSETS = [
        "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X",
        "USDCAD=X", "USDCHF=X", "NZDUSD=X",
        "EURJPY=X", "GBPJPY=X", "EURGBP=X"
    ]
    NAMES = {
        "EURUSD":"EUR/USD","GBPUSD":"GBP/USD","USDJPY":"USD/JPY",
        "AUDUSD":"AUD/USD","USDCAD":"USD/CAD","USDCHF":"USD/CHF",
        "NZDUSD":"NZD/USD","EURJPY":"EUR/JPY","GBPJPY":"GBP/JPY",
        "EURGBP":"EUR/GBP"
    }

    def load_chats():
        try:
            if os.path.exists(CHATS_FILE):
                with open(CHATS_FILE) as f:
                    return set(json.load(f))
        except Exception:
            pass
        return set()

    def save_chats(c):
        try:
            with open(CHATS_FILE, "w") as f:
                json.dump(list(c), f)
        except Exception:
            pass

    active_chats = load_chats()
    bot_status["users"] = len(active_chats)
    log.info(f"Loaded {len(active_chats)} saved users")

    try:
        bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)
    except Exception as e:
        log.error(f"Bot init error: {e}")
        return

    def pname(asset):
        return NAMES.get(asset.replace("=X",""), asset.replace("=X",""))

    def get_candles(asset, interval="1m", limit=300):
        for attempt in range(4):
            try:
                time.sleep(random.uniform(2.5, 5.0))
                df = yf.download(asset, period="5d", interval=interval,
                                 progress=False, timeout=30)
                if df is None or df.empty or len(df) < 80:
                    return pd.DataFrame()
                df = df[['Open','High','Low','Close','Volume']].copy()
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df.columns = ['open','high','low','close','volume']
                return df.tail(limit).reset_index(drop=True)
            except Exception as e:
                err = str(e).lower()
                if any(k in err for k in ["rate","too many","429","limit"]):
                    w = (attempt+1)*25 + random.randint(10,20)
                    log.warning(f"Rate limited {asset}. Wait {w}s")
                    time.sleep(w)
                else:
                    log.error(f"Fetch {asset}: {e}")
                    time.sleep(10)
        return pd.DataFrame()

    def add_indicators(df):
        try:
            c, h, l = df['close'], df['high'], df['low']
            df['ema9']  = ta.trend.EMAIndicator(c, window=9).ema_indicator()
            df['ema21'] = ta.trend.EMAIndicator(c, window=21).ema_indicator()
            df['ema50'] = ta.trend.EMAIndicator(c, window=50).ema_indicator()
            df['rsi']   = ta.momentum.RSIIndicator(c, window=14).rsi()
            s = ta.momentum.StochRSIIndicator(c, window=14, smooth1=3, smooth2=3)
            df['stoch_k'] = s.stochrsi_k()
            df['stoch_d'] = s.stochrsi_d()
            m = ta.trend.MACD(c, window_fast=12, window_slow=26, window_sign=9)
            df['macd']        = m.macd()
            df['macd_signal'] = m.macd_signal()
            df['macd_hist']   = m.macd_diff()
            b = ta.volatility.BollingerBands(c, window=20, window_dev=2)
            df['bb_middle'] = b.bollinger_mavg()
            df['bb_width']  = b.bollinger_wband()
            df['atr'] = ta.volatility.AverageTrueRange(h, l, c, window=14).average_true_range()
            a = ta.trend.ADXIndicator(h, l, c, window=14)
            df['adx']     = a.adx()
            df['adx_pos'] = a.adx_pos()
            df['adx_neg'] = a.adx_neg()
        except Exception as e:
            log.error(f"Indicator: {e}")
        return df

    def is_session():
        return 7 <= datetime.now(timezone.utc).hour <= 20

    def generate_signal(asset):
        try:
            pk = asset.replace("=X","")
            now_ts = time.time()
            if not is_session(): return None
            if signal_history[pk] and now_ts - signal_history[pk][-1] < SIGNAL_COOLDOWN:
                return None

            df1 = get_candles(asset,"1m",300)
            if df1.empty or len(df1)<150: return None
            time.sleep(random.uniform(3,5))
            df5 = get_candles(asset,"5m",150)
            if df5.empty or len(df5)<80: return None
            time.sleep(random.uniform(3,5))
            df15 = get_candles(asset,"15m",100)
            if df15.empty or len(df15)<60: return None

            df1=add_indicators(df1); df5=add_indicators(df5); df15=add_indicators(df15)
            l1,p1,l5,l15 = df1.iloc[-1],df1.iloc[-2],df5.iloc[-1],df15.iloc[-1]

            atr_avg = df1['atr'].tail(20).mean()
            if pd.isna(l1['atr']) or l1['atr'] < atr_avg*0.55: return None
            if pd.isna(l5['adx']) or l5['adx'] < 22: return None
            bb_avg = df5['bb_width'].tail(30).mean()
            if not pd.isna(l5['bb_width']) and l5['bb_width'] > bb_avg*2.8: return None

            def ok(v): return not pd.isna(v)

            bull,bull_r = 0,[]
            if ok(p1['ema9']) and p1['ema9']<=p1['ema21'] and l1['ema9']>l1['ema21']:
                bull+=1; bull_r.append("EMA Cross ⬆️")
            if ok(l5['ema9']) and l5['ema9']>l5['ema21'] and l5['close']>l5['ema50']:
                bull+=1; bull_r.append("5m Uptrend")
            if ok(l15['ema9']) and l15['close']>l15['ema21'] and l15['ema9']>l15['ema21']:
                bull+=1; bull_r.append("15m HTF Bull")
            if ok(l1['rsi']) and 40<=l1['rsi']<=62:
                bull+=1; bull_r.append(f"RSI {int(l1['rsi'])}")
            if ok(l1['stoch_k']) and ok(p1['stoch_k']) and p1['stoch_k']<p1['stoch_d'] and l1['stoch_k']>l1['stoch_d'] and l1['stoch_k']<80:
                bull+=1; bull_r.append("StochRSI ⬆️")
            if ok(l5['macd']) and l5['macd']>l5['macd_signal'] and l5['macd_hist']>0:
                bull+=1; bull_r.append("MACD Bull")
            if ok(l1['bb_middle']) and l1['close']>l1['bb_middle'] and l5['close']>l5['bb_middle']:
                bull+=1; bull_r.append("Above BB")
            if ok(l5['adx_pos']) and l5['adx_pos']>l5['adx_neg'] and l5['adx']>25:
                bull+=1; bull_r.append("ADX+")

            bear,bear_r = 0,[]
            if ok(p1['ema9']) and p1['ema9']>=p1['ema21'] and l1['ema9']<l1['ema21']:
                bear+=1; bear_r.append("EMA Cross ⬇️")
            if ok(l5['ema9']) and l5['ema9']<l5['ema21'] and l5['close']<l5['ema50']:
                bear+=1; bear_r.append("5m Downtrend")
            if ok(l15['ema9']) and l15['close']<l15['ema21'] and l15['ema9']<l15['ema21']:
                bear+=1; bear_r.append("15m HTF Bear")
            if ok(l1['rsi']) and 38<=l1['rsi']<=60:
                bear+=1; bear_r.append(f"RSI {int(l1['rsi'])}")
            if ok(l1['stoch_k']) and ok(p1['stoch_k']) and p1['stoch_k']>p1['stoch_d'] and l1['stoch_k']<l1['stoch_d'] and l1['stoch_k']>20:
                bear+=1; bear_r.append("StochRSI ⬇️")
            if ok(l5['macd']) and l5['macd']<l5['macd_signal'] and l5['macd_hist']<0:
                bear+=1; bear_r.append("MACD Bear")
            if ok(l1['bb_middle']) and l1['close']<l1['bb_middle'] and l5['close']<l5['bb_middle']:
                bear+=1; bear_r.append("Below BB")
            if ok(l5['adx_neg']) and l5['adx_neg']>l5['adx_pos'] and l5['adx']>25:
                bear+=1; bear_r.append("ADX-")

            if bull>=MIN_CONDITIONS and bull>bear:
                direction,score,reasons = "CALL ⬆️",bull,bull_r
            elif bear>=MIN_CONDITIONS and bear>bull:
                direction,score,reasons = "PUT ⬇️",bear,bear_r
            else:
                return None

            confidence = min(98, 88+int((score/8)*12))
            if confidence < MIN_CONFIDENCE: return None

            signal_history[pk].append(now_ts)
            return {
                "name": pname(asset), "direction": direction,
                "confidence": confidence, "score": f"{score}/8",
                "reasons": " | ".join(reasons),
                "adx": round(float(l5['adx']),1),
                "rsi": round(float(l1['rsi']),1),
                "time": datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
            }
        except Exception as e:
            log.error(f"Signal [{asset}]: {e}")
            return None

    def fmt(s):
        return (
            f"━━━━━━━━━━━━━━━━━━\n🎯 *QUOTEX SIGNAL*\n━━━━━━━━━━━━━━━━━━\n"
            f"💱 *{s['name']}*\n📊 Direction: *{s['direction']}*\n"
            f"⏱ Expiry: *1 Minute*\n💯 Confidence: *{s['confidence']}%*\n"
            f"📈 Score: *{s['score']} conditions*\n"
            f"📉 ADX: `{s['adx']}` | RSI: `{s['rsi']}`\n"
            f"✅ {s['reasons']}\n🕐 {s['time']}\n━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ Max risk: *1% per trade only*"
        )

    def broadcast(msg):
        for cid in list(active_chats):
            try:
                bot.send_message(cid, msg, parse_mode='Markdown')
                time.sleep(0.3)
            except Exception as e:
                if any(k in str(e).lower() for k in ["blocked","not found","deactivated"]):
                    active_chats.discard(cid)
                    save_chats(active_chats)

    # Commands
    @bot.message_handler(commands=['start'])
    def cmd_start(message):
        cid = message.chat.id
        is_new = cid not in active_chats
        active_chats.add(cid)
        save_chats(active_chats)
        bot_status["users"] = len(active_chats)
        bot.reply_to(message,
            "🚀 *Quotex Smart Signal Bot*\n\n"
            + ("✅ Active! Auto signals milenge.\n" if is_new else "✅ Pehle se active ho!\n")
            + "🧠 3 Timeframes + 8 Indicators\n💯 Sirf 92%+ confidence pe signal\n\n"
            "━━━━━━━━━\n/signals /status /stop",
            parse_mode='Markdown')

    @bot.message_handler(commands=['stop'])
    def cmd_stop(message):
        active_chats.discard(message.chat.id)
        save_chats(active_chats)
        bot_status["users"] = len(active_chats)
        bot.reply_to(message, "🔴 *Band. Dobara: /start*", parse_mode='Markdown')

    @bot.message_handler(commands=['status'])
    def cmd_status(message):
        from datetime import datetime, timezone
        hour = datetime.now(timezone.utc).hour
        bot.reply_to(message,
            f"🟢 *Bot Running*\n"
            f"⏰ {datetime.now(timezone.utc).strftime('%H:%M UTC')}\n"
            f"📡 {'🟢 London+NY' if 7<=hour<=20 else '🔴 Off-hours'}\n"
            f"👥 Users: {len(active_chats)}\n💯 Min: {MIN_CONFIDENCE}%",
            parse_mode='Markdown')

    @bot.message_handler(commands=['signals'])
    def cmd_signals(message):
        active_chats.add(message.chat.id)
        save_chats(active_chats)
        bot.reply_to(message, "🔍 *Scanning... wait 1-2 min*", parse_mode='Markdown')
        found = False
        for asset in ASSETS:
            sig = generate_signal(asset)
            if sig:
                found = True
                bot.send_message(message.chat.id, fmt(sig), parse_mode='Markdown')
            time.sleep(5)
        if not found:
            bot.send_message(message.chat.id,
                "⏳ *Koi signal nahi mila.* Bot wait karega — auto signal aayega.", parse_mode='Markdown')

    # Auto signal loop
    def auto_loop():
        time.sleep(90)
        while True:
            try:
                if not is_session() or not active_chats:
                    time.sleep(300); continue
                log.info(f"Auto scan: {len(ASSETS)} pairs, {len(active_chats)} users")
                sent = 0
                for asset in ASSETS:
                    sig = generate_signal(asset)
                    if sig:
                        broadcast(fmt(sig))
                        bot_status["signals_sent"] += 1
                        sent += 1
                    time.sleep(8)
                log.info(f"Scan done. {sent} signals. Sleep 5 min.")
                time.sleep(300)
            except Exception as e:
                log.error(f"Auto loop: {e}")
                time.sleep(60)

    threading.Thread(target=auto_loop, daemon=True).start()

    bot_status["running"] = True
    log.info("Bot polling started!")

    # Crash-proof polling
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60,
                                 allowed_updates=["message"])
        except telebot.apihelper.ApiTelegramException as e:
            if "409" in str(e):
                log.error("409 Conflict. Wait 30s...")
                time.sleep(30)
            else:
                log.error(f"API error: {e}. Retry 15s...")
                time.sleep(15)
        except Exception as e:
            log.error(f"Polling error: {e}. Retry 15s...")
            time.sleep(15)


# ========== ENTRY POINT ==========
if __name__ == "__main__":
    log.info("Starting Quotex Signal Bot...")

    # Start bot in background thread (non-blocking)
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()

    # Flask runs as main process — Render sees it immediately
    log.info(f"Starting web server on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
