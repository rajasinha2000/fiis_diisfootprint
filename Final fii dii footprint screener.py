import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# ===================== CONFIG =====================
st.set_page_config(page_title="Market Dashboard", layout="wide")
st_autorefresh(interval=900_000, key="refresh_15min")

# ===================== ALERT STATE =====================
if "alerts_enabled" not in st.session_state:
    st.session_state.alerts_enabled = False

# ===================== ALERT BADGE =====================
def alert_status_badge(enabled):
    return f"""
    <div style="padding:8px;border-radius:10px;
        background-color:{'#d4edda' if enabled else '#f8d7da'};
        color:{'#155724' if enabled else '#721c24'};
        font-weight:bold;font-size:18px;text-align:center;">
        {'🔔 Telegram Alerts: ON ✅' if enabled else '🔕 Telegram Alerts: OFF ❌'}
    </div>
    """

st.markdown(alert_status_badge(st.session_state.alerts_enabled), unsafe_allow_html=True)

# ===================== TITLE =====================
st.title("📈 Triple Supertrend + Bollinger Breakout Screener")

# ===================== SIDEBAR =====================
st.sidebar.header("⚙️ Alert Control")

if st.sidebar.button("▶️ Start Alerts"):
    st.session_state.alerts_enabled = True

if st.sidebar.button("⏹️ Stop Alerts"):
    st.session_state.alerts_enabled = False

# ===================== SYMBOL LIST =====================
stock_list = [
    "HDFCBANK.NS", "RELIANCE.NS", "MARUTI.NS",
    "^NSEI", "^NSEBANK",
    "BTC-USD", "ETH-USD"
]

# ===================== SUPERTREND =====================
def supertrend(df, period=10, multiplier=3):
    df = df.copy()
    df["TR"] = df[["High","Low","Close"]].max(axis=1) - df[["High","Low","Close"]].min(axis=1)
    df["ATR"] = df["TR"].rolling(period).mean()
    hl2 = (df["High"] + df["Low"]) / 2
    df["UB"] = hl2 + multiplier * df["ATR"]
    df["LB"] = hl2 - multiplier * df["ATR"]

    trend = [True]
    for i in range(1, len(df)):
        if trend[-1]:
            trend.append(df["Close"].iloc[i] >= df["LB"].iloc[i-1])
        else:
            trend.append(df["Close"].iloc[i] > df["UB"].iloc[i-1])

    df["Supertrend"] = trend
    return df

# ===================== BOLLINGER =====================
def bollinger_signal(df, length=20, mult=1):
    df = df.copy()
    df["MB"] = df["Close"].rolling(length).mean()
    df["STD"] = df["Close"].rolling(length).std()
    df["UB"] = df["MB"] + mult * df["STD"]
    df["LB"] = df["MB"] - mult * df["STD"]

    if len(df) < length + 2:
        return "NO_BB"

    pc, lc = df["Close"].iloc[-2], df["Close"].iloc[-1]
    pub, lub = df["UB"].iloc[-2], df["UB"].iloc[-1]
    plb, llb = df["LB"].iloc[-2], df["LB"].iloc[-1]

    if pc <= pub and lc > lub:
        return "BB_UP"
    elif pc >= plb and lc < llb:
        return "BB_DOWN"
    else:
        return "NO_BB"

# ===================== DATA FETCH =====================
@st.cache_data(ttl=900)
def fetch_data(symbol, interval, period):
    try:
        df = yf.download(symbol, interval=interval, period=period, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["High","Low","Close"]].dropna()
        return df
    except:
        return pd.DataFrame()

# ===================== ANALYZE =====================
def analyze(symbol):
    tfs = {"1m":"2d", "3m":"5d", "15m":"1mo"}
    dfs = {}
    for tf, per in tfs.items():
        df = fetch_data(symbol, tf, per)
        if not df.empty:
            dfs[tf] = df

    if len(dfs) < 3:
        return None

    signals = {}
    bb_1m = bb_3m = "NO_BB"

    for tf, df in dfs.items():
        st_df = supertrend(df)
        signals[tf] = "🟢 Bullish" if st_df["Supertrend"].iloc[-1] else "🔴 Bearish"

        if tf == "1m":
            bb_1m = bollinger_signal(df)
        if tf == "3m":
            bb_3m = bollinger_signal(df)

    cmp_price = round(dfs["15m"]["Close"].iloc[-1], 2)

    if len(set(signals.values())) == 1:
        trend = list(signals.values())[0]

        if trend == "🟢 Bullish" and (bb_1m == "BB_UP" or bb_3m == "BB_UP"):
            final = "🚀 BUY | Triple ST + BB Breakout"
        elif trend == "🔴 Bearish" and (bb_1m == "BB_DOWN" or bb_3m == "BB_DOWN"):
            final = "🔻 SELL | Triple ST + BB Breakdown"
        else:
            final = "⏸️ Triple ST (No BB)"
    else:
        final = "⏸️ Mixed"

    return {
        "Symbol": symbol.replace(".NS","").replace("^",""),
        "CMP": cmp_price,
        "1m ST": signals["1m"],
        "3m ST": signals["3m"],
        "15m ST": signals["15m"],
        "BB 1m": bb_1m,
        "BB 3m": bb_3m,
        "Final Signal": final
    }

# ===================== TELEGRAM =====================
def send_telegram(msg):
    token = "7735892458:AAELFRclang2MgJwO2Rd9RRwNmoll1LzlFg"
    chat_id = "5073531512"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, data={"chat_id":chat_id,"text":msg})

# ===================== MAIN =====================
rows = []
for s in stock_list:
    res = analyze(s)
    if res:
        rows.append(res)

df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True)

# ===================== ALERT =====================
alerts = df[df["Final Signal"].str.contains("BUY|SELL", na=False)]

if not alerts.empty:
    st.warning("🚨 VALID TRIPLE ST + BB ALERTS 🚨")

    for _, r in alerts.iterrows():
        msg = (
            f"🚨 TRIPLE ST + BB ALERT 🚨\n\n"
            f"📌 {r['Symbol']}\n"
            f"💰 CMP: {r['CMP']}\n"
            f"📈 {r['Final Signal']}\n"
            f"⏱ 1m | 3m | 15m"
        )
        st.write(msg.replace("\n"," | "))

        if st.session_state.alerts_enabled:
            send_telegram(msg)

st.caption(f"⏰ Last Updated: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}")

