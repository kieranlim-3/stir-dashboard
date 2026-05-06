# ── loaders/nyfed_loader.py ───────────────────────────────────────────────────
# Real loader for EFFR and SOFR from FRED (St. Louis Fed).
# These are FREE — no API key or subscription needed.
# Drop this function in place of make_mock_ref_rates() in dashboard.py.
# ─────────────────────────────────────────────────────────────────────────────

import pandas as pd
from datetime import date

# FRED CSV download URLs — no API key required
EFFR_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=EFFR"
SOFR_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=SOFR"

def load_ref_rates(today: date) -> pd.DataFrame:
    """
    Pull EFFR and SOFR from FRED (St. Louis Fed) public CSV endpoint.
    Returns a DataFrame with columns [effr, sofr] indexed by business date.
    """
    effr = (pd.read_csv(EFFR_URL, parse_dates=["observation_date"])
              .set_index("observation_date")["EFFR"]
              .rename("effr")
              .dropna()
              .astype(float)
              .sort_index())

    sofr = (pd.read_csv(SOFR_URL, parse_dates=["observation_date"])
              .set_index("observation_date")["SOFR"]
              .rename("sofr")
              .dropna()
              .astype(float)
              .sort_index())

    ref = pd.concat([effr, sofr], axis=1).dropna()
    return ref


# ── USAGE ─────────────────────────────────────────────────────────────────────
# In dashboard.py, replace:
#   ref_rates = make_mock_ref_rates(TODAY)
# With:
#   from loaders.nyfed_loader import load_ref_rates
#   ref_rates = load_ref_rates(TODAY)
