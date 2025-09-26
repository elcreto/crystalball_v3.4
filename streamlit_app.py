
import time
import streamlit as st
import yfinance as yf
import pandas as pd

APP_NAME = "🔮 Crystal Ball v3.4 — EID (Fixed)"
st.set_page_config(page_title=APP_NAME, layout="wide")
st.title(APP_NAME)
st.caption("v3.4 with rate‑limit handling, explicit yfinance params, and pandas .item() fixes.")

DEFAULT_TICKERS = "MSFT,ETN,MDT,IONQ,MU,META,ONTO,NBIS"

with st.sidebar:
    st.subheader("Settings")
    tickers_text = st.text_area("Tickers (comma separated)", DEFAULT_TICKERS, height=100)
    vol_mult = st.number_input("Volume multiple (≥)", min_value=1.0, value=1.5, step=0.1)
    rr_min = st.number_input("Min R/R", min_value=1.0, value=2.0, step=0.5)
    risk_pct = st.number_input("Risk per trade (%)", min_value=0.1, value=1.0, step=0.1)
    sleep_s = st.number_input("Sleep between downloads (sec)", min_value=0.0, value=0.6, step=0.1)
    max_retries = st.slider("Max retries per ticker", 0, 5, 3)

tickers = [t.strip().upper() for t in tickers_text.split(",") if t.strip()]

@st.cache_data(show_spinner=False)
def fetch(ticker: str, retries: int = 3, sleep: float = 0.6):
    """Download daily OHLCV with retries to reduce YF rate-limit errors."""
    last_err = None
    for i in range(retries + 1):
        try:
            df = yf.download(
                ticker,
                period="6mo",
                interval="1d",
                progress=False,
                auto_adjust=False,  # explicit to silence warning
                threads=False       # sequential requests help avoid rate limits
            )
            if df is not None and not df.empty:
                return df
        except Exception as e:
            last_err = e
        import time as _t; _t.sleep(sleep * (i + 1))  # linear backoff
    raise RuntimeError(f"Failed to download {ticker}: {last_err}")

rows = []
failures = []

for t in tickers:
    try:
        data = fetch(t, retries=max_retries, sleep=sleep_s)
        if data.empty:
            failures.append((t, "empty dataframe"))
            continue

        # EMAs
        data["EMA20"] = data["Close"].ewm(span=20).mean()
        data["EMA50"] = data["Close"].ewm(span=50).mean()

        # Volume check
        avg_vol = data["Volume"].rolling(20).mean()
        vol_ok = bool(data["Volume"].iloc[-1].item() >= vol_mult * avg_vol.iloc[-1].item())

        # Trend check
        trend_ok = bool(
            data["EMA20"].iloc[-1].item() > data["EMA50"].iloc[-1].item()
            and data["Close"].iloc[-1].item() > data["EMA20"].iloc[-1].item()
        )

        # Risk/Reward calc (basic): stop at EMA50, target at >= rr_min * risk distance
        entry = float(data["Close"].iloc[-1].item())
        stop = float(data["EMA50"].iloc[-1].item())
        if stop <= 0 or entry <= stop:
            rr_ok = False
            target = None
            rr = None
            risk_dist = None
        else:
            risk_dist = entry - stop
            target = entry + rr_min * risk_dist
            rr = (target - entry) / (risk_dist if risk_dist else 1.0)
            rr_ok = rr >= rr_min

        # Catalyst placeholder
        catalyst = False

        score = sum([trend_ok, vol_ok, rr_ok, catalyst])
        if score >= 3:
            status = "Prime" if score == 4 else "Candidate"
            rows.append({
                "Ticker": t,
                "Entry": round(entry, 2),
                "Stop": round(stop, 2) if stop else None,
                "Target": round(target, 2) if target else None,
                "RiskDist": round(risk_dist, 2) if risk_dist else None,
                "R/R": round(rr, 2) if rr else None,
                "TrendOK": trend_ok,
                "VolOK": vol_ok,
                "RROK": rr_ok,
                "Catalyst": catalyst,
                "Score": int(score),
                "Status": status,
            })
    except Exception as e:
        failures.append((t, str(e)))

st.subheader("Results")
if rows:
    df = pd.DataFrame(rows).sort_values(["Status","Score","R/R"], ascending=[True, False, False])
    st.dataframe(df, use_container_width=True)
    # Export buttons
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV", data=csv, file_name="crystalball_v34_results.csv", mime="text/csv")
    try:
        import io
        with pd.ExcelWriter("crystalball_v34_results.xlsx", engine="xlsxwriter") as writer:
            pd.DataFrame(rows).to_excel(writer, index=False, sheet_name="results")
        with open("crystalball_v34_results.xlsx", "rb") as f:
            st.download_button("⬇️ Download Excel", data=f, file_name="crystalball_v34_results.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as _:
        st.info("Install xlsxwriter to enable Excel export.")
else:
    st.warning("No valid candidates with current criteria. Adjust tickers or thresholds.")

if failures:
    with st.expander("Show download warnings/errors"):
        for t, msg in failures:
            st.write(f"- {t}: {msg}")
