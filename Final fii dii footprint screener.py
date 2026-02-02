import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# ===================== CONFIG =====================
st.set_page_config(page_title="Market Dashboard", layout="wide")
st_autorefresh(interval=900_000, key="refresh_15min")  # Refresh every 15 mins

# ===================== ALERT STATUS INDICATOR =====================
if "alerts_enabled" not in st.session_state:
    st.session_state.alerts_enabled = False

def alert_status_badge(enabled: bool):
    if enabled:
        return """
        <div style="padding:8px; border-radius:10px; background-color:#d4edda; color:#155724; 
                    font-weight:bold; font-size:18px; width:100%; text-align:center;">
            🔔 Telegram Alerts: ON ✅
        </div>
        """
    else:
        return """
        <div style="padding:8px; border-radius:10px; background-color:#f8d7da; color:#721c24; 
                    font-weight:bold; font-size:18px; width:100%; text-align:center;">
            🔕 Telegram Alerts: OFF ❌
        </div>
        """

st.markdown(alert_status_badge(st.session_state.alerts_enabled), unsafe_allow_html=True)

# ===================== TITLE =====================
st.title("📈 Triple Supertrend Screener (1m, 3m, 15m) + 3m SMA Signals")

# ===================== SIDEBAR ALERT CONTROL =====================
st.sidebar.header("⚙️ Alert Controls")
if st.sidebar.button("▶️ Start Alerts"):
    st.session_state.alerts_enabled = True
    st.sidebar.success("Telegram Alerts ENABLED ✅")

if st.sidebar.button("⏹️ Stop Alerts"):
    st.session_state.alerts_enabled = False
    st.sidebar.warning("Telegram Alerts DISABLED ❌")

# ===================== STOCK LIST =====================
index_list = ["^NSEI", "^NSEBANK"]

crypto_list = ["BTC-USD", "ETH-USD"]

stock_list = [
    "HDFCBANK.NS","RELIANCE.NS","MARUTI.NS"
] + index_list + crypto_list


# ===================== SUPER TREND FUNCTION =====================
def supertrend(df, period=10, multiplier=3):
    df = df.copy()
    df['High'] = df['High'].astype(float)
    df['Low'] = df['Low'].astype(float)
    df['Close'] = df['Close'].astype(float)

    # True Range & ATR
    df['H-L'] = df['High'] - df['Low']
    df['H-PC'] = abs(df['High'] - df['Close'].shift(1))
    df['L-PC'] = abs(df['Low'] - df['Close'].shift(1))
    df['TR'] = df[['H-L','H-PC','L-PC']].max(axis=1)
    df['ATR'] = df['TR'].rolling(period).mean()

    hl2 = (df['High'] + df['Low']) / 2
    df['Upper Basic'] = hl2 + multiplier * df['ATR']
    df['Lower Basic'] = hl2 - multiplier * df['ATR']
    df['Upper Band'] = df['Upper Basic']
    df['Lower Band'] = df['Lower Basic']

    trend = [True]  # start bullish
    for i in range(1, len(df)):
        prev_trend = trend[-1]

        if prev_trend:
            if df['Close'].iloc[i] < df['Lower Band'].iloc[i-1]:
                trend.append(False)
            else:
                trend.append(True)
                df.loc[df.index[i], 'Lower Band'] = max(df['Lower Band'].iloc[i], df['Lower Band'].iloc[i-1])
        else:
            if df['Close'].iloc[i] > df['Upper Band'].iloc[i-1]:
                trend.append(True)
            else:
                trend.append(False)
                df.loc[df.index[i], 'Upper Band'] = min(df['Upper Band'].iloc[i], df['Upper Band'].iloc[i-1])

    df['Supertrend'] = trend
    return df

# ===================== SMA FUNCTION =====================
def sma_signal(df, period=20):
    df = df.copy()
    df["SMA"] = df["Close"].rolling(period).mean()
    last_close = df["Close"].iloc[-1]
    last_sma = df["SMA"].iloc[-1]

    if last_close > last_sma:
        return "📈 SMA Breakout"
    elif last_close < last_sma:
        return "📉 SMA Breakdown"
    else:
        return "⏸️ Near SMA"

# ===================== DATA FETCH FUNCTION =====================
@st.cache_data(ttl=900)
def fetch_data(symbol, interval, lookback="2d"):
    intervals_to_try = [interval]
    if interval == "1m": intervals_to_try.append("5m")
    if interval == "3m": intervals_to_try.append("5m")
    if interval == "15m": intervals_to_try.append("30m")

    for i in intervals_to_try:
        try:
            df = yf.download(symbol, interval=i, period=lookback, progress=False)
            if not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df = df[['High','Low','Close']].astype(float)
                df = df.tz_localize(None)
                return df
        except Exception as e:
            print(f"{symbol} fetch error ({i}): {e}")
    return pd.DataFrame()

# ===================== ANALYSIS FUNCTION =====================
def analyze(symbol):
    timeframes = {"1m": "2d", "3m": "5d", "15m": "1mo"}
    dfs = {}
    for tf, period in timeframes.items():
        df = fetch_data(symbol, tf, lookback=period)
        if not df.empty:
            dfs[tf] = df

    if not dfs:
        return {
            "Stock": symbol.replace(".NS","").replace("^",""),
            "CMP": None,
            "1m Trend":"No Data",
            "3m Trend":"No Data",
            "15m Trend":"No Data",
            "3m SMA Signal":"No Data",
            "Final Signal":"⚠️ No Data"
        }

    signals = {}
    cmp_price = round(list(dfs.values())[-1]["Close"].iloc[-1], 2)
    sma_3m = "No Data"

    for tf, df_tf in dfs.items():
        df_st = supertrend(df_tf, period=10, multiplier=3)
        last = df_st.iloc[-1]
        signals[tf] = "🟢 Bullish" if bool(last["Supertrend"]) else "🔴 Bearish"

        if tf == "3m":
            sma_3m = sma_signal(df_tf, period=20)

    if len(set(signals.values())) == 1:
        final_signal = f"✅ Triple Supertrend {list(signals.values())[0]}"
    else:
        final_signal = "⏸️ Mixed"

    for tf in ["1m","3m","15m"]:
        if tf not in signals: signals[tf] = "No Data"

    return {
        "Stock": symbol.replace(".NS","").replace("^",""),
        "CMP": cmp_price,
        "1m Trend": signals["1m"],
        "3m Trend": signals["3m"],
        "15m Trend": signals["15m"],
        "3m SMA Signal": sma_3m,
        "Final Signal": final_signal
    }

# ===================== TELEGRAM ALERT FUNCTION =====================
def send_telegram_alert(message):
    token = "7735892458:AAELFRclang2MgJwO2Rd9RRwNmoll1LzlFg"
    chat_id = "5073531512"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        requests.post(url, data=payload)
    except:
        pass

# ===================== MAIN LOOP =====================
results = []
progress_bar = st.progress(0)
status_text = st.empty()
last_refresh = st.empty()

for i, stock in enumerate(stock_list, 1):
    status_text.text(f"Processing {i}/{len(stock_list)}: {stock}...")
    try:
        res = analyze(stock)
        results.append(res)
    except Exception as e:
        print(f"{stock} error: {e}")
    progress_bar.progress(i / len(stock_list))

progress_bar.empty()
status_text.empty()
last_refresh.markdown(f"⏰ Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

df_result = pd.DataFrame(results)

if not df_result.empty:
    # ===================== COLOR-CODED STYLING =====================
    def highlight_trend(val):
        if "Bullish" in val: return "color: green; font-weight:bold"
        elif "Bearish" in val: return "color: red; font-weight:bold"
        elif "Breakout" in val: return "color: green; font-weight:bold"
        elif "Breakdown" in val: return "color: red; font-weight:bold"
        elif "Mixed" in val: return "color: orange; font-weight:bold"
        elif "No Data" in val: return "color: gray; font-style:italic"
        else: return ""

    st.dataframe(
        df_result.style.applymap(
            highlight_trend,
            subset=["1m Trend", "3m Trend", "15m Trend", "3m SMA Signal", "Final Signal"]
        ),
        use_container_width=True
    )

    # ===================== COMBINED ALERTS =====================
    alerts = df_result[
    df_result["Final Signal"].str.contains("Triple Supertrend")
]


    if st.checkbox("Show Alerts Only"):
        st.dataframe(alerts, use_container_width=True)

    if not alerts.empty:
        st.warning("🚨 Combined Alerts Found!")
        for _, row in alerts.iterrows():
            alert_msg = (
                f"🚨 TRIPLE SUPERTREND ALERT 🚨\n\n"
                f"📢 Symbol: {row['Stock']}\n"
                f"💰 CMP: {row['CMP']}\n"
                f"📈 Signal: {row['Final Signal']}\n"
                f"⏱ Timeframes: 1m | 3m | 15m"
            )
            st.write(alert_msg.replace("\n", "  |  "))

            if st.session_state.alerts_enabled:
                send_telegram_alert(alert_msg)

    # ===================== DOWNLOAD OPTION =====================
    csv = df_result.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📂 Download Screener CSV",
        data=csv,
        file_name="supertrend_screener.csv",
        mime="text/csv"
    )

else:
    st.warning("⚠️ No valid data found.")






