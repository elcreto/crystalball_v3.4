# Crystal Ball v3.4 — MACD / MACD‑V Toggle

Strict TA filter with optional MACD mode:
- Trend alignment (EMA20 > EMA50 & Close > EMA20)
- Volume ≥ N × 20d average (default 1.5×)
- Risk/Reward ≥ threshold (default 2R, stop at EMA50, target = entry + R×risk)

MACD toggle is provided for context and display:
- Classic MACD
- MACD‑V (volume‑weighted, via VWEMA)

## Run
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```
