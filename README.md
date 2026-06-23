# 🚀 Quotex Pro Signal Bot v4.0

An automated, high-precision Telegram bot designed to generate binary options trading signals for Quotex using real-time market data. Built with Python, `yfinance`, and `pandas-ta`, it analyzes multiple timeframes to identify institutional-grade setups based on key technical indicators.

---

## 🌟 Key Features

* **Multi-Timeframe Analysis:** Dynamically tracks and processes **1-minute (1m)** entry execution candles alongside **5-minute (5m)** higher timeframe trend confirmations.
* **High Accuracy Filter:** Features a built-in strict filter (`MIN_CONFIDENCE = 88`) to ignore low-probability setups.
* **Smart Cooldown Engine:** Employs a 5-minute tracking cooldown per currency pair to avoid spamming multiple signals during a single market movement.
* **Session Guard:** Automatically restricts signal generation outside active market hours, optimizing focus primarily during the **London & New York sessions** (07:00 - 21:00 UTC).
* **Dual Mode:** Operates as both an on-demand command bot and a continuous background automated channel broadcaster using multi-threading.

---

## 📈 Supported Assets

The bot continuously scans 15 major Forex pairs:
`EUR/USD`, `GBP/USD`, `USD/JPY`, `AUD/USD`, `USD/CAD`, `USD/CHF`, `NZD/USD`, `EUR/JPY`, `GBPJPY`, `EUR/GBP`, `AUD/JPY`, `EUR/CAD`, `GBP/AUD`, `USD/INR`, `EUR/INR`.

---

## 🛠️ Technical Strategy Architecture

The core signal engine calculates standard indicators on every iteration and requires structural alignment across indicators:

* **EMA Crossover:** Tracks Fast `EMA(9)` and Slow `EMA(21)` crossover/crossunder on the 1-minute chart.
* **RSI (Relative Strength Index):** Length 14 filter to prevent entries into extreme overbought (>65 for calls) or oversold (<35 for puts) zones.
* **MACD:** Verifies structural momentum alignment between the MACD Line and Signal Line.
* **Bollinger Bands:** Validates whether price has broken and sustains above/below the 20-period Basis Moving Average line (`BBM_20_2.0`).
* **HTF Confirmation:** Validates that the 5-minute close aligns with the major trend direction over its 21-period EMA.

---

## 🤖 Bot Commands

| Command | Action / Description |
| :--- | :--- |
| `/start` | Launches the welcome interface and showcases bot capabilities. |
| `/status` | Fetches active runtime state and synchronizes current synchronized Quotex Server Time (UTC). |
| `/signals` | Triggers a live manual scan across all 15 major assets for instantaneous setups. |
| `/future` | Displays anticipated high-probability market setups developing over the next 30-45 minutes. |

---

## 🚀 Quick Start Guide

### 1. Prerequisites
Ensure you have Python 3.8+ installed on your environment.

### 2. Installation
Clone this repository and install the mandatory dependencies:

```bash
git clone [https://github.com/yourusername/quotex-pro-bot.git](https://github.com/yourusername/quotex-pro-bot.git)
cd quotex-pro-bot
pip install pyTelegramBotAPI pandas pandas-ta yfinance
