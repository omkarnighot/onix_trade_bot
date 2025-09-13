# Onix Trade Bot

![Python](https://img.shields.io/badge/Python-3.8%2B-yellow?style=for-the-badge)

## 📈 Overview

**Onix Trade Bot** scans NIFTY50 stocks for price proximity to their 44-period moving average (44MA) on multiple intraday intervals. If a stock’s price is near its MA and the MA is trending up, it is flagged as a candidate. All candidate stocks are notified via Telegram as a CSV file.

---

## 🚦 Features

- **44-period Moving Average Scan**  
  - Checks NIFTY50 stocks over intraday intervals (15m, 30m, 45m, 60m).
  - Flags stocks where the price is near the 44MA and the MA is trending up.
- **Telegram Notification**  
  - Sends a CSV of candidate stocks to a configured Telegram chat.

---

## ⚙️ Configuration

Set the following environment variables for Telegram integration:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

---

## 🚀 Usage

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the scanner:**
   ```bash
   python scanner.py
   ```

---

## 📂 How It Works

- Downloads intraday data for NIFTY50 symbols.
- Calculates the 44-period moving average of the Close price.
- Flags symbols where:
  - The moving average slope is positive (trending up).
  - The price is within a configurable percentage of the 44MA.
- Sends results as a CSV file via Telegram.

---

> **Note:** This project currently supports only 44MA scanning and Telegram notifications for NIFTY50 stocks.
