import time
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

APP_NAME = "🔮 Crystal Ball v3.4 — MACD‑V Only (Strict TA)"
st.set_page_config(page_title=APP_NAME, layout="wide")
st.title(APP_NAME)
st.caption("Strict pass/fail on Trend, Volume, R/R. MACD‑V shown for context.")

DEFAULT_TICKERS = "MSFT,ETN,MDT,IONQ,MU,META,ONTO,NBIS,INTC"

with st.sidebar:
    st.subheader("Settings")
    tickers_text = st.text_area("Tickers (comma separated)", DEFAULT_TICKERS, height=90)
    vol_mult = st.number_input("Volume multiple (≥)", min_value=1.0, value=1.5, step=0.1)
    rr_min = st.number_input("Min R/R", min_value=1.0, value=2.0, step=0.5)
    sleep_s = st.number_input("Sleep between downloads (sec)", min_value=0.0, value=0.6, step=0.1)
    max_retries = st.slider("Max retries per ticker", 0, 5, 3)

tickers = [t.strip().upper() for t in tickers_text.split(",") if t.strip()]

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
def fetch(ticker: str, retries: int = 3, sleep: float = 0.6):
    last_err = None
    for i in range(retries + 1):
        try:
            df = yf.download(
                ticker,
                period="6mo",
                interval="1d",
                progress=False,
                auto_adjust=False,
                threads=False
            )
            if df is not None and not df.empty:
                return df
        except Exception as e:
            last_err = e
        time.sleep(sleep * (i + 1))
    raise RuntimeError(f"Failed to download {ticker}: {last_err}")

def to_float(x):
    try:
        if hasattr(x, "item"):
            return float(x.item())
        return float(x)
    except Exception:
        return float("nan")

rows, failures = [], []

for t in tickers:
    try:
        data = fetch(t, retries=max_retries, sleep=sleep_s)
        if data is None or data.empty:
            failures.append((t, "empty dataframe")); continue

        close = data["Close"]
        vol = data["Volume"].fillna(0)

        ema20 = close.ewm(span=20, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()

        c_last = to_float(close.iloc[-1]); e20 = to_float(ema20.iloc[-1]); e50 = to_float(ema50.iloc[-1])
        avg_vol = vol.rolling(20).mean(); v_last = to_float(vol.iloc[-1]); v_avg = to_float(avg_vol.iloc[-1])

        trend_ok = (not np.isnan(e20) and not np.isnan(e50) and not np.isnan(c_last)) and (e20 > e50) and (c_last > e20)
        vol_ok   = (not np.isnan(v_avg)) and (v_avg > 0) and (v_last >= vol_mult * v_avg)

        # MACD‑V context
        _, _, hist_v = macd_v(close, vol)
        h_last = to_float(hist_v.iloc[-1])
        macdv_note = "Bullish" if h_last > 0 else ("Bearish" if h_last < 0 else "Flat")

        # R/R strict (stop=EMA50)
        entry = c_last; stop = e50
        if (not np.isfinite(stop)) or (stop <= 0) or (not np.isfinite(entry)) or (entry <= stop):
            rr_ok = False; target = None; rr = None
        else:
            risk_dist = entry - stop
            target = entry + rr_min * risk_dist
            rr = (target - entry) / risk_dist if risk_dist else float("nan")
            rr_ok = np.isfinite(rr) and (rr >= rr_min)

        score = int(bool(trend_ok)) + int(bool(vol_ok)) + int(bool(rr_ok))
        status = "Prime" if score == 3 else ("Candidate" if score == 2 else "Fail")

        rows.append({
            "Ticker": t,
            "Entry": round(entry, 2) if np.isfinite(entry) else None,
            "Stop": round(stop, 2) if np.isfinite(stop) else None,
            "Target": round(target, 2) if (target is not None and np.isfinite(target)) else None,
            "R/R": round(rr, 2) if (rr is not None and np.isfinite(rr)) else None,
            "TrendOK": bool(trend_ok),
            "VolOK": bool(vol_ok),
            "RROK": bool(rr_ok),
            "Score (0-3)": score,
            "Status": status,
            "MACD‑V": macdv_note
        })
    except Exception as e:
        failures.append((t, str(e)))

st.subheader("Results")
if rows:
    df = pd.DataFrame(rows).sort_values(by=["Score (0-3)", "R/R"], ascending=[False, False])
    st.dataframe(df, use_container_width=True)
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV", data=csv, file_name="crystalball_v34_macdv_only_results.csv", mime="text/csv")
else:
    st.warning("No valid candidates with current criteria. Try different tickers or thresholds.")

if failures:
    with st.expander("Download warnings/errors"):
        for t, msg in failures:
            st.write(f"- {t}: {msg}")
