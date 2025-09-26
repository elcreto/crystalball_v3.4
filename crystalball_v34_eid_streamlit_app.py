import streamlit as st
import yfinance as yf
import pandas as pd

APP_NAME = "🔮 Crystal Ball v3.4 — EID Streamlit App"

st.set_page_config(page_title=APP_NAME, layout="wide")
st.title(APP_NAME)

st.caption("v3.4 rules: Trend alignment (EMA20>EMA50 & price>EMA20), Volume ≥ 1.5× 20d avg, R/R ≥ 2, optional Catalyst score.")

# --- Parameters ---
tickers = st.text_area("Enter tickers (comma separated)", 
                       "MSFT,ETN,MDT,IONQ,MU,META,ONTO,NBIS").split(",")
tickers = [t.strip().upper() for t in tickers if t.strip() != ""]

results = []

for t in tickers:
    try:
        data = yf.download(t, period="6mo", interval="1d", progress=False)
        if data.empty:
            continue

        # EMAs
        data["EMA20"] = data["Close"].ewm(span=20).mean()
        data["EMA50"] = data["Close"].ewm(span=50).mean()

        # Volume check
        avg_vol = data["Volume"].rolling(20).mean()
        vol_ok = data["Volume"].iloc[-1] >= 1.5 * avg_vol.iloc[-1]

        # Trend check
        trend_ok = data["EMA20"].iloc[-1] > data["EMA50"].iloc[-1] and                    data["Close"].iloc[-1] > data["EMA20"].iloc[-1]

        # Risk/Reward calculation (basic)
        entry = float(data["Close"].iloc[-1])
        stop = float(data["EMA50"].iloc[-1])
        if stop <= 0 or entry <= stop:
            rr_ok = False
            target = None
        else:
            target = entry + 2 * (entry - stop)  # 2R target
            rr_ok = (target - entry) / (entry - stop) >= 2

        # Catalyst placeholder (manual/news API integration later)
        catalyst = False

        # Score
        score = sum([trend_ok, vol_ok, rr_ok, catalyst])
        if score >= 3:
            status = "Prime" if score == 4 else "Candidate"
            results.append([t, round(entry, 2), round(stop, 2), 
                            round(target, 2) if target else None, score, status])
    except Exception as e:
        st.error(f"Error processing {t}: {e}")

# Display
if results:
    df = pd.DataFrame(results, columns=["Ticker", "Entry", "Stop", "Target", "Score", "Status"])
    st.subheader("Results")
    st.dataframe(df, use_container_width=True)
else:
    st.warning("No valid candidates found with current criteria.")
