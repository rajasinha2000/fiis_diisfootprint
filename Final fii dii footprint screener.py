import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# ================= CONFIG =================
st.set_page_config(page_title="Crypto BB + Triple ST", layout="wide")
st_autorefresh(interval=300_000, key="refresh_5min")

# ================= STATE =================
if "alerts_enabled" not in st.session_state:
    st.session_state.alerts_enabled = False

# ================= TITLE =================
st.title("🚀 BTC & ETH – 1m / 3m BB(20,1) + Triple Supertrend")

# ================= SIDEBAR =================
st.sidebar.header("⚙️ Alerts")
if st.sidebar.button("▶️ Start Alerts"):
    st.session_state.alerts_enabled = True
if st.sidebar.button("⏹️ Stop Alerts"):
    st.session_state.alerts_enabled = False

# ================= SYMBOLS =================
symbols = ["BTC-USD", "ETH-USD"]

# ================= DATA =================
@st.cache_data(ttl=300)
def fetch(symbol, interval, period):
    df = yf.download(symbol, interval=interval, period=period, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df[["High","Low","Close"]].dropna()

# ================= SUPERTREND =================
def supertrend(df, period=10, mult=3):
    df = df.copy()
    hl2 = (df["High"] + df["Low"]) / 2
    tr = pd.concat([
        df["High"] - df["Low"],
        abs(df["High"] - df["Close"].shift()),
        abs(df["Low"] - df["Close"].shift())
    ], axis=1).max(axis=1)

    atr = tr.rolling(period).mean()
    upper = hl2 + mult * atr
    lower = hl2 - mult * atr

    trend = [True]
    for i in range(1, len(df)):
        if trend[-1]:
            trend.append(df["Close"].iloc[i] >= lower.iloc[i-1])
        else:
            trend.append(df["Close"].iloc[i] > upper.iloc[i-1])

    df["ST"] = trend
    return df

# ================= BOLLINGER =================
def bb_cross(df, length=20, mult=1):
    mb = df["Close"].rolling(length).mean()
    sd = df["Close"].rolling(length).std()
    ub = mb + mult * sd
    lb = mb - mult * sd

    if len(df) < length + 2:
        return "NO"

    prev = df["Close"].iloc[-2]
    curr = df["Close"].iloc[-1]

    if prev <= ub.iloc[-2] and curr > ub.iloc[-1]:
        return "UP"
    if prev >= lb.iloc[-2] and curr < lb.iloc[-1]:
        return "DOWN"
    return "NO"

# ================= ANALYSIS =================
def analyze(symbol):
    df_1m = fetch(symbol, "1m", "1d")
    df_3m = fetch(symbol, "3m", "3d")
    df_15m = fetch(symbol, "15m", "5d")

    if df_1m.empty or df_3m.empty or df_15m.empty:
        return None

    st1 = supertrend(df_1m)["ST"].iloc[-1]
    st3 = supertrend(df_3m)["ST"].iloc[-1]
    st15 = supertrend(df_15m)["ST"].iloc[-1]

    bb1 = bb_cross(df_1m)
    bb3 = bb_cross(df_3m)

    cmp_price = round(df_1m["Close"].iloc[-1], 2)

    if st1 == st3 == st15:
        if st1 and (bb1 == "UP" or bb3 == "UP"):
            final = "🚀 BUY – BB(20,1) Breakout"
        elif not st1 and (bb1 == "DOWN" or bb3 == "DOWN"):
            final = "🔻 SELL – BB(20,1) Breakdown"
        else:
            final = "⏸️ Triple ST (No BB)"
    else:
        final = "⏸️ Mixed Trend"

    return {
        "Symbol": symbol.replace("-USD",""),
        "CMP": cmp_price,
        "1m ST": "Bull" if st1 else "Bear",
        "3m ST": "Bull" if st3 else "Bear",
        "15m ST": "Bull" if st15 else "Bear",
        "BB 1m": bb1,
        "BB 3m": bb3,
        "Final Signal": final
    }

# ================= TELEGRAM =================
def send_telegram(msg):
    token = "7735892458:AAELFRclang2MgJwO2Rd9RRwNmoll1LzlFg"
    chat_id = "5073531512"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": msg})

# ================= MAIN =================
rows = []
for s in symbols:
    r = analyze(s)
    if r:
        rows.append(r)

df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True)

alerts = df[df["Final Signal"].str.contains("BUY|SELL", na=False)]

if not alerts.empty:
    st.warning("🚨 BB(20,1) + TRIPLE ST SIGNAL 🚨")
    for _, r in alerts.iterrows():
        msg = f"""
🚨 CRYPTO ALERT 🚨
{r['Symbol']}
CMP: {r['CMP']}
{r['Final Signal']}
TF: 1m | 3m | 15m
"""
        st.write(msg.replace("\n"," | "))
        if st.session_state.alerts_enabled:
            send_telegram(msg)

st.caption(f"⏰ Updated: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}")
