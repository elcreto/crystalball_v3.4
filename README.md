# Crystal Ball v3.4 — MACD / MACD‑V (Fixed Scalars)

Fixes ambiguous Series truth errors by forcing scalar casts with `.iloc[-1]` and `float()`,
and guarding all comparisons with `np.isnan/np.isfinite`.

## Run
```
pip install -r requirements.txt
streamlit run streamlit_app.py
```
