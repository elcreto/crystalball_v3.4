# Crystal Ball v3.4 — EID Streamlit App

**Name fixed to correct format**: `crystalball_v34_eid_streamlit_app.py`

Implements v3.4 rules:
- Trend alignment (EMA20>EMA50 & price>EMA20)
- Volume ≥ 1.5× 20-day avg
- Risk/Reward ≥ 2 (stop near EMA50; basic target = 2R)
- Optional Catalyst flag (stubbed for future integration)

## Run
```bash
pip install -r requirements.txt
streamlit run crystalball_v34_eid_streamlit_app.py
```
