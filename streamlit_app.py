import time
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

APP_NAME = "🔮 Crystal Ball v3.4 — MACD / MACD‑V Toggle"
st.set_page_config(page_title=APP_NAME, layout="wide")
st.title(APP_NAME)
st.caption("Strict TA filter with switchable MACD mode. Rules: Trend (EMA20>EMA50 & Close>EMA20), Volume ≥ N×20d avg, R/R ≥ threshold. Optional catalyst placeholder.")

DEFAULT_TICKERS = "MSFT,ETN,MDT,IONQ,MU,META,ONTO,NBIS,INTC"

with st.sidebar:
    st.subheader("Settings")
    tickers_text = st.text_area("Tickers (comma separated)", DEFAULT_TICKERS, height=90)
    macd_mode = st.selectbox("MACD Mode", ["Classic MACD", "MACD‑V (Volume‑weighted)"])
    vol_mult = st.number_input("Volume multiple (≥)", min_value=1.0, value=1.5, step=0.1)
    rr_min = st.number_input("Min R/R", min_value=1.0, value=2.0, step=0.5)
    sleep_s = st.number_input("Sleep between downloads (sec)", min_value=0.0, value=0.6, step=0.1)
    max_retries = st.slider("Max retries per ticker", 0, 5, 3)

tickers = [t.strip().upper() for t in tickers_text.split(",") if t.strip()]

# ---------- Indicators ----------
def macd_classic(series: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

def vwema(price: pd.Series, volume: pd.Series, span: int) -> pd.Series:
    # Volume‑weighted EMA: EMA(V*P) / EMA(V)
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
def fetch(ticker: str, retries: int = 3, sleep: float = 0.6):
    last_err = None
    for i in range(retries + 1):
        try:
            df = yf.download(
                ticker,
                period="6mo",
                interval="1d",
                progress=False,
                auto_adjust=False,  # explicit
                threads=False       # sequential to reduce rate limits
            )
            if df is not None and not df.empty:
                return df
        except Exception as e:
            last_err = e
        time.sleep(sleep * (i + 1))
    raise RuntimeError(f"Failed to download {ticker}: {last_err}")

rows = []
failures = []

for t in tickers:
    try:
        data = fetch(t, retries=max_retries, sleep=sleep_s)
        if data.empty:
            failures.append((t, "empty dataframe"))
            continue

        close = data["Close"]
        vol = data["Volume"].fillna(0)

        # EMAs
        ema20 = close.ewm(span=20, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()

        # Volume check
        avg_vol = vol.rolling(20).mean()
        v_last = float(vol.iloc[-1])
        v_avg = float(avg_vol.iloc[-1]) if avg_vol.iloc[-1] > 0 else float("nan")
        vol_ok = (not np.isnan(v_avg)) and (v_last >= vol_mult * v_avg)

        # Trend check
        c_last = float(close.iloc[-1])
        e20 = float(ema20.iloc[-1])
        e50 = float(ema50.iloc[-1])
        trend_ok = (e20 > e50) and (c_last > e20)

        # MACD (for display only; Crystal Ball's decision uses trend/vol/RR; MACD shown in notes)
        if macd_mode == "Classic MACD":
            macd_line, sig_line, hist = macd_classic(close)
        else:
            macd_line, sig_line, hist = macd_v(close, vol)
        m_last, s_last = float(macd_line.iloc[-1]), float(sig_line.iloc[-1])
        h_last, h_prev = float(hist.iloc[-1]), float(hist.iloc[-2])
        macd_ok = (m_last > s_last) and (h_last > 0) and (h_last > h_prev)

        # Risk/Reward calc (strict): stop at EMA50, target at >= rr_min * risk distance
        entry = c_last
        stop = e50
        if stop <= 0 or entry <= stop or not np.isfinite(stop):
            rr_ok = False
            target = None
            rr = None
            risk_dist = None
        else:
            risk_dist = entry - stop
            target = entry + rr_min * risk_dist
            rr = (target - entry) / (risk_dist if risk_dist else 1.0)
            rr_ok = rr >= rr_min

        # Catalyst placeholder (Crystal Ball stays TA‑strict; catalyst not counted)
        catalyst = False

        # Score (Crystal Ball strict: 3 checks only — trend, volume, RR)
        score = int(trend_ok) + int(vol_ok) + int(rr_ok)
        if score == 3:
            status = "Prime"
        elif score == 2:
            status = "Candidate"
        else:
            status = "Fail"

        rows.append({
            "Ticker": t,
            "Entry": round(entry, 2),
            "Stop": round(stop, 2) if stop else None,
            "Target": round(target, 2) if target else None,
            "R/R": round(rr, 2) if rr else None,
            "TrendOK": trend_ok,
            "VolOK": vol_ok,
            "RROK": rr_ok,
            "Score (0-3)": score,
            "Status": status,
            "MACD Mode": macd_mode,
            "MACD OK": macd_ok
        })
    except Exception as e:
        failures.append((t, str(e)))

st.subheader("Results")
if rows:
    df = pd.DataFrame(rows).sort_values(["Status","Score (0-3)","R/R"], ascending=[True, False, False])
    st.dataframe(df, use_container_width=True)
    # Export buttons
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV", data=csv, file_name="crystalball_v34_macdv_results.csv", mime="text/csv")
else:
    st.warning("No valid candidates with current criteria. Adjust tickers or thresholds.")

if failures:
    with st.expander("Download warnings/errors"):
        for t, msg in failures:
            st.write(f"- {t}: {msg}")
