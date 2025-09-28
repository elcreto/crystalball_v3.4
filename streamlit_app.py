import time
import pandas as pd
import numpy as np
import streamlit as st
import yfinance as yf

APP_NAME = "📈 S&P 500 Scanner v3.5 — MACD/MACD‑V (Patched)"
st.set_page_config(page_title=APP_NAME, layout="wide")
st.title(APP_NAME)
st.caption("0–5 scoring with Catalyst awareness + MACD/MACD‑V toggle. Includes Streamlit Cloud patch (fileWatcherType=poll).")

# -----------------------------
# Sidebar settings
# -----------------------------
with st.sidebar:
    st.subheader("Settings")
    macd_mode = st.selectbox("MACD Mode", ["Classic MACD", "MACD‑V (Volume‑weighted)"])
    vol_mult = st.number_input("Volume multiple (vs 20‑day avg) ≥", min_value=1.0, value=1.3, step=0.1)
    rr_min = st.number_input("Min Risk/Reward", min_value=1.0, value=2.0, step=0.5)
    max_universe = st.number_input("Max tickers to scan", min_value=20, value=60, step=10)
    sleep_s = st.number_input("Sleep between downloads (sec)", min_value=0.0, value=0.3, step=0.1)
    retries = st.slider("Max retries per ticker", 0, 5, 2)
    days = st.slider("Lookback period (days)", 90, 365, 180)
    export_filename = st.text_input("Export base filename", "sp500_scan_v35")

# -----------------------------
# Indicators
# -----------------------------
def macd_classic(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

def vwema(price: pd.Series, volume: pd.Series, span: int) -> pd.Series:
    vp = (price * volume).ewm(span=span, adjust=False).mean()
    v = volume.ewm(span=span, adjust=False).mean().replace(0, np.nan)
    return vp / v

def macd_v(price: pd.Series, volume: pd.Series, fast=12, slow=26, signal=9):
    vw_fast = vwema(price, volume, fast)
    vw_slow = vwema(price, volume, slow)
    macd_line = vw_fast - vw_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

@st.cache_data(show_spinner=False)
def fetch_one(ticker: str, period_days: int, retries: int, sleep: float):
    last_err = None
    for i in range(retries + 1):
        try:
            df = yf.download(
                ticker,
                period=f"{period_days}d",
                interval="1d",
                progress=False,
                auto_adjust=False,
                threads=False,
            )
            if df is not None and not df.empty:
                return df
        except Exception as e:
            last_err = e
        time.sleep(sleep * (i + 1))
    return pd.DataFrame()

# -----------------------------
# Universe
# -----------------------------
EMBEDDED_SP500 = ["AAPL","MSFT","GOOGL","AMZN","META","NVDA","BRK-B","UNH","XOM","LLY","JPM","V","MA","HD",
"PG","COST","JNJ","MRK","PEP","KO","BAC","ADBE","WMT","NFLX","CRM","TMO","AVGO","CVX","LIN","TXN","PFE","ABT",
"CSCO","ACN","AMD","MCD","DHR","INTC","INTU","QCOM","LOW","AMGN","PM","HON","AMAT","BMY","IBM","GE","GS","CAT",
"NOW","BA","ISRG","BKNG","MDT","RTX","BLK","SPGI","PLD","DE","AMT","SYK","LMT","SCHW","MS","ADI","GILD","MU",
"ETN","ONTO","IONQ","META"]

universe = EMBEDDED_SP500[: int(max_universe)]

# -----------------------------
# Scan loop
# -----------------------------
rows, failures = [], []
progress = st.progress(0)

for idx, t in enumerate(universe, start=1):
    try:
        data = fetch_one(t, days, retries, sleep_s)
        if data.empty or len(data) < 60:
            continue

        close = data["Close"]
        vol = data["Volume"].fillna(0)

        ema20 = close.ewm(span=20, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()

        c_last = float(close.iloc[-1])
        e20, e50 = float(ema20.iloc[-1]), float(ema50.iloc[-1])

        trend_ok = (e20 > e50) and (c_last > e20)

        if macd_mode == "Classic MACD":
            macd_line, sig_line, hist = macd_classic(close)
        else:
            macd_line, sig_line, hist = macd_v(close, vol)

        m_last, s_last = float(macd_line.iloc[-1]), float(sig_line.iloc[-1])
        h_last, h_prev = float(hist.iloc[-1]), float(hist.iloc[-2])
        macd_ok = (m_last > s_last) and (h_last > 0) and (h_last > h_prev)

        vol_avg20 = vol.rolling(20).mean()
        v_last, v_avg = float(vol.iloc[-1]), float(vol_avg20.iloc[-1])
        vol_ok = (v_avg > 0) and (v_last >= vol_mult * v_avg)

        entry, stop = c_last, e50
        if stop > 0 and entry > stop:
            risk = entry - stop
            target = entry + rr_min * risk
            rr = (target - entry) / risk
            rr_ok = rr >= rr_min
        else:
            target, rr, rr_ok = None, None, False

        catalyst, catalyst_reason = False, "—"
        score = int(trend_ok) + int(macd_ok) + int(vol_ok) + int(rr_ok) + int(catalyst)

        status, notes = "Pass", ""
        if score >= 3:
            if score == 5:
                status, notes = "PRIME", "Clean TA + Catalyst"
            elif score == 4 and catalyst:
                status, notes = "Catalyst PRIME", "News-driven"
            elif score == 4:
                status, notes = "Strong TA", "Clean technicals"
            elif score == 3:
                status, notes = "Candidate", "Early setup"

            rows.append({
                "Ticker": t,
                "Entry": round(entry, 2),
                "Stop(EMA50)": round(stop, 2) if stop else None,
                "Target": round(target, 2) if target else None,
                "R/R": round(rr, 2) if rr else None,
                "Score (0-5)": score,
                "Status": status,
                "Catalyst": catalyst_reason,
                "Notes": notes,
                "MACD Mode": macd_mode,
            })
    except Exception as e:
        failures.append((t, str(e)))
    if idx % 5 == 0 or idx == len(universe):
        progress.progress(idx / len(universe))

# -----------------------------
# Output
# -----------------------------
if rows:
    df = pd.DataFrame(rows).sort_values(["Score (0-5)","Status"], ascending=[False, True])
    st.subheader("Results")
    st.dataframe(df, use_container_width=True)
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV", data=csv, file_name=f"{export_filename}.csv", mime="text/csv")
else:
    st.warning("No candidates found. Try loosening thresholds or increasing universe size.")

if failures:
    with st.expander("Fetch errors"):
        for t, msg in failures:
            st.write(f"- {t}: {msg}")
