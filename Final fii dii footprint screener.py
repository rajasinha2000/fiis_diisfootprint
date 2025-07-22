import streamlit as st
import pandas as pd
import yfinance as yf
import datetime
import requests
import os
import json

# --- CONFIG ---
REFRESH_INTERVAL_MIN = 5
ENABLE_TELEGRAM = True
TELEGRAM_TOKEN = "7735892458:AAELFRclang2MgJwO2Rd9RRwNmoll1LzlFg"
TELEGRAM_CHAT_ID = "5073531512"
ALERT_LOG_FILE = "alert_log.json"

st.set_page_config(layout="wide", page_title="FII/DII Footprint Screener")
st.title("\U0001F4CA FII/DII Footprint Screener Dashboard")
st.caption(f"\U0001F501 Auto-refresh every {REFRESH_INTERVAL_MIN} minutes.")

symbols = [    "RELIANCE", "HDFCBANK", "INFY", "TCS", "ICICIBANK",
    "LT", "SBIN", "KOTAKBANK", "AXISBANK", "BSE",
    "BHARTIARTL", "TITAN", "ASIANPAINT", "OFSS", "MARUTI",
    "BOSCHLTD", "TRENT", "NESTLEIND", "ULTRACEMCO", "MCX",
    "CAMS", "COFORGE","HAL","KEI"
]

# Load alert log to prevent duplicate alerts
if os.path.exists(ALERT_LOG_FILE):
    with open(ALERT_LOG_FILE, "r") as f:
        alert_log = json.load(f)
else:
    alert_log = {}

def save_alert_log(log):
    with open(ALERT_LOG_FILE, "w") as f:
        json.dump(log, f)

@st.cache_data(ttl=REFRESH_INTERVAL_MIN * 60)
def fetch_data(symbol):
    try:
        df = yf.download(symbol + ".NS", period="15d", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < 10:
            return None

        df["EMA20"] = df["Close"].ewm(span=20).mean()
        df["MACD"] = df["Close"].ewm(span=12).mean() - df["Close"].ewm(span=26).mean()
        df["Signal"] = df["MACD"].ewm(span=9).mean()
        df["RSI"] = compute_rsi(df["Close"])

        prev_close = df["Close"].iloc[-2].item()
        today_close = df["Close"].iloc[-1].item()
        today_volume = df["Volume"].iloc[-1].item()
        avg_volume = df["Volume"].iloc[-6:-1].mean().item()
        recent_high = df["Close"].iloc[-6:-1].max().item()

        delivery_perc = round((today_volume / avg_volume) * 100, 2)
        breakout = today_close > recent_high
        volume_surge = today_volume > 1.5 * avg_volume
        price_strength = today_close > prev_close * 1.01

        rsi = df["RSI"].iloc[-1]
        macd = df["MACD"].iloc[-1]
        macd_signal = df["Signal"].iloc[-1]

        rsi_signal = "Overbought" if rsi > 70 else "Oversold" if rsi < 30 else "Neutral"
        macd_signal_type = "Bullish" if macd > macd_signal else "Bearish"

        long_buildup = today_close > prev_close and today_volume > avg_volume
        short_buildup = today_close < prev_close and today_volume > avg_volume

        signal = "BUY" if all([breakout, volume_surge, price_strength, macd > macd_signal]) else \
                 "SELL" if price_strength and macd < macd_signal else "AVOID"
        action = "\U0001F4C8 Buy" if signal == "BUY" else "\U0001F4C9 Sell" if signal == "SELL" else "\u23F8\uFE0F Wait"

        alert_key = f"{symbol}_{signal}"
        if ENABLE_TELEGRAM and signal in ["BUY", "SELL"] and alert_key not in alert_log:
            msg = f"""\U0001F9E0 *FII/DII Footprint Alert*
*{symbol}* \u25B6\uFE0F {signal}
CMP: ₹{today_close:.2f}
Volume: {int(today_volume):,} (Avg: {int(avg_volume):,})
Delivery%: {delivery_perc}%
Breakout: {"\u2705" if breakout else "\u274C"}
MACD: {macd_signal_type}
RSI: {rsi_signal}
Long Buildup: {"\u2705" if long_buildup else "-"}
Short Buildup: {"\u2705" if short_buildup else "-"}
Action: {action}"""
            send_telegram_alert(msg)
            alert_log[alert_key] = str(datetime.datetime.now())

        return {
            "Symbol": symbol,
            "CMP": round(today_close, 2),
            "Prev Close": round(prev_close, 2),
            "Avg Volume": int(avg_volume),
            "Today Vol": int(today_volume),
            "Delivery %": delivery_perc,
            "Breakout": breakout,
            "Vol Surge": volume_surge,
            "Price Strength": price_strength,
            "MACD": macd_signal_type,
            "RSI": rsi_signal,
            "Long Buildup": "\u2705" if long_buildup else "",
            "Short Buildup": "\u2705" if short_buildup else "",
            "Signal": signal,
            "Action": action
        }

    except Exception:
        st.warning(f"\u26A0\uFE0F Failed to fetch data for {symbol}")
        return None

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def send_telegram_alert(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        requests.post(url, data=payload)
    except Exception:
        st.warning("\u26A0\uFE0F Telegram alert failed.")

# --- MAIN VIEW ---
st.markdown("### \U0001F50D Screener Results")
results = []

for symbol in symbols:
    row = fetch_data(symbol)
    if row:
        results.append(row)

save_alert_log(alert_log)

if results:
    df = pd.DataFrame(results)

    def highlight_missing(val):
        return "background-color: yellow" if pd.isna(val) else ""

    styled_df = df.style.map(highlight_missing)
    st.dataframe(styled_df, use_container_width=True)

    st.download_button("\U0001F4C5 Download CSV", data=df.to_csv(index=False), file_name="fii_dii_signals.csv")
else:
    st.warning("\u26A0\uFE0F No data returned or API limit reached.")

# --- Auto-refresh JS ---
st.caption(f"\U0001F552 Last updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

st.markdown(f"""
    <script>
        setTimeout(function() {{
            window.location.reload();
        }}, {REFRESH_INTERVAL_MIN * 60 * 1000});
    </script>
""", unsafe_allow_html=True)
