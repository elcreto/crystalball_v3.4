
# Crystal Ball v3.4 — EID (Fixed)

Fixes:
- yfinance `auto_adjust=False` (silence warning)
- sequential requests (`threads=False`) + retry/backoff to reduce rate limits
- `.item()` for pandas scalars (deprecation-safe)
- CSV/Excel export + sidebar controls

## Run
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```
