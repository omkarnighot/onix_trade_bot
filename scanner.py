import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import io
import requests

# ---- Config ----
NEAR_PCT = 1.0        # "near MA" threshold in % (change to 0.5 if you want tighter)
PERIOD = "7d"         # lookback period for intraday
NIFTY50 = [
    "ADANIENT.NS","ADANIPORTS.NS","APOLLOHOSP.NS","ASIANPAINT.NS","AXISBANK.NS",
    "BAJAJ-AUTO.NS","BAJFINANCE.NS","BAJAJFINSV.NS","BEL.NS","BPCL.NS",
    "BHARTIARTL.NS","BRITANNIA.NS","CIPLA.NS","COALINDIA.NS","DIVISLAB.NS",
    "DRREDDY.NS","EICHERMOT.NS","GRASIM.NS","HCLTECH.NS","HDFCBANK.NS",
    "HDFCLIFE.NS","HEROMOTOCO.NS","HINDALCO.NS","HINDUNILVR.NS","ICICIBANK.NS",
    "ITC.NS","INDUSINDBK.NS","INFY.NS","JSWSTEEL.NS","KOTAKBANK.NS",
    "LT.NS","M&M.NS","MARUTI.NS","NESTLEIND.NS","NTPC.NS",
    "ONGC.NS","POWERGRID.NS","RELIANCE.NS","SBILIFE.NS","SBIN.NS",
    "SUNPHARMA.NS","TCS.NS","TATACONSUM.NS","TATAMOTORS.NS","TATASTEEL.NS",
    "TECHM.NS","TITAN.NS","ULTRACEMCO.NS","UPL.NS","WIPRO.NS"
]

# ---- Telegram Config ----
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN"  # replace with your bot token
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"      # replace with your chat ID

# ---- Helper Functions ----
def safe_download(sym, interval_used):
    """Download intraday for a single symbol, return DataFrame or (None, reason)."""
    try:
        df = yf.download(sym, period=PERIOD, interval=interval_used, progress=False, auto_adjust=False)
    except Exception as e:
        return None, f"download_error:{e}"
    if df is None or df.empty:
        return None, "no_data"
    if "Close" not in df.columns:
        cand = [c for c in df.columns if "close" in str(c).lower()]
        if len(cand) == 1:
            df = df.rename(columns={cand[0]: "Close"})
        else:
            return df, f"missing_close_cols:{list(df.columns)}"
    return df, None

def make_45m_from_15m(df15):
    """Resample 15m df into 45T bars safely even if some OHLC/Volume missing."""
    cols = set(df15.columns)
    if {"Open","High","Low","Close"}.issubset(cols):
        agg = {"Open":"first","High":"max","Low":"min","Close":"last"}
        if "Volume" in cols:
            agg["Volume"] = "sum"
        df45 = df15.resample("45T").agg(agg).dropna()
        if "Volume" not in df45.columns:
            df45["Volume"] = 0
        return df45
    else:
        s = df15["Close"].resample("45T")
        df45 = s.agg(['first','max','min','last']).dropna()
        df45.columns = ["Open","High","Low","Close"]
        if "Volume" in df15.columns:
            df45["Volume"] = df15["Volume"].resample("45T").sum().reindex(df45.index).fillna(0)
        else:
            df45["Volume"] = 0
        return df45

def analyze_symbol(sym, interval_label):
    """Analyze single symbol for given interval. Returns info dict or None + reason."""
    download_interval = "15m" if interval_label == "45m" else interval_label
    df_raw, reason = safe_download(sym, download_interval)
    if df_raw is None and reason:
        return None, reason
    if isinstance(df_raw, pd.DataFrame) and df_raw.empty:
        return None, "empty_df"

    df = df_raw.copy()
    try:
        if interval_label == "45m":
            df = make_45m_from_15m(df)
    except Exception as e:
        return None, f"resample_error:{e}"

    if "Close" not in df.columns:
        return None, f"no_close_after_resample:{list(df.columns)}"
    if len(df) < 10:
        return None, f"too_few_rows:{len(df)}"

    df["MA44"] = df["Close"].rolling(window=44).mean()
    if df["MA44"].dropna().empty:
        return None, f"insufficient_ma44_rows:{len(df)}"

    last_close = float(df["Close"].iloc[-1])
    last_ma = float(df["MA44"].iloc[-1])
    prev_close = float(df["Close"].iloc[-2]) if len(df) >= 2 else np.nan
    ma_non_na = df["MA44"].dropna()
    prev_ma = float(ma_non_na.iloc[-2]) if len(ma_non_na) >= 2 else np.nan
    recent_ma = ma_non_na.iloc[-6:].to_numpy() if len(ma_non_na) >= 1 else np.array([])
    slope = float(np.diff(recent_ma).mean()) if recent_ma.size >= 2 else np.nan
    diff_pct = float((last_close - last_ma) / last_ma * 100) if np.isfinite(last_ma) and last_ma != 0 else np.nan

    info = {
        "symbol": sym,
        "interval": interval_label,
        "rows": len(df),
        "last_close": last_close,
        "prev_close": prev_close,
        "last_ma": last_ma,
        "prev_ma": prev_ma,
        "diff_pct": diff_pct,
        "slope": slope,
        "recent_ma": recent_ma.tolist()
    }

    info["is_candidate"] = np.isfinite(slope) and slope > 0 and np.isfinite(diff_pct) and abs(diff_pct) <= NEAR_PCT
    return info, None

def send_csv_telegram(df, filename="44ma_candidates.csv"):
    """Send DataFrame as CSV file to Telegram."""
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)
    files = {'document': (filename, csv_buffer)}
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    data = {'chat_id': TELEGRAM_CHAT_ID}
    response = requests.post(url, data=data, files=files)
    if response.status_code == 200:
        print("✅ CSV sent successfully via Telegram")
    else:
        print("❌ Failed to send CSV via Telegram:", response.text)

# ---- Main Scan Function ----
def run_scan(intervals = ["15m","30m","45m","60m"]):
    all_matches = []
    for iv in intervals:
        print("\n" + "="*60)
        print(f"🔎 Scanning interval: {iv}")
        print("="*60)
        for sym in NIFTY50:
            info, reason = analyze_symbol(sym, iv)
            if info is None:
                print(f"❌ {sym:12} — {reason}")
                continue

            print(f"{sym:12} rows={info['rows']:2d} | close={info['last_close']:8.2f} prev={info['prev_close']:8.2f} | MA44={info['last_ma']:8.2f} prev_MA={info['prev_ma']:8.2f} | Δ%={info['diff_pct']:6.2f} | slope={info['slope']: .6f} | cand={info['is_candidate']}")
            if info["is_candidate"]:
                all_matches.append(info)

    print("\n" + "="*60)
    print("📌 Summary of candidates (near MA & MA trending up):")
    if not all_matches:
        print("🚫 No matches found with current threshold/settings.")
    else:
        results = [[m['symbol'], m['interval'], m['last_close'], m['last_ma'], m['diff_pct'], m['slope']] for m in all_matches]
        cols = ["Symbol", "Interval", "Price", "MA44", "Delta_%", "Slope"]
        df = pd.DataFrame(results, columns=cols)
        print(df.to_string(index=False))
        send_csv_telegram(df)

# ---- Run ----
if __name__ == "__main__":
    run_scan()
