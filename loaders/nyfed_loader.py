# ── loaders/nyfed_loader.py ───────────────────────────────────────────────────
# Real loader for EFFR and SOFR from the New York Fed.
# These are FREE — no API key or subscription needed.
# Drop this function in place of make_mock_ref_rates() in dashboard.py.
# ─────────────────────────────────────────────────────────────────────────────

import pandas as pd
from datetime import date

EFFR_URL = "https://markets.newyorkfed.org/read?productCode=50&startDate=2020-01-01&endDate={end}&eventCodes=500&format=csv"
SOFR_URL = "https://markets.newyorkfed.org/read?productCode=50&startDate=2020-01-01&endDate={end}&eventCodes=520&format=csv"

def load_ref_rates(today: date) -> pd.DataFrame:
    """
    Pull EFFR and SOFR from the NY Fed public CSV endpoint.
    Returns a DataFrame with columns [effr, sofr] indexed by business date.
    """
    end_str = today.strftime("%Y-%m-%d")

    effr_raw = pd.read_csv(EFFR_URL.format(end=end_str), parse_dates=["effectiveDate"])
    sofr_raw = pd.read_csv(SOFR_URL.format(end=end_str), parse_dates=["effectiveDate"])

    effr = (effr_raw.set_index("effectiveDate")["percentRate"]
                    .rename("effr")
                    .sort_index())

    sofr = (sofr_raw.set_index("effectiveDate")["percentRate"]
                    .rename("sofr")
                    .sort_index())

    ref = pd.concat([effr, sofr], axis=1).dropna()
    return ref


# ── USAGE ─────────────────────────────────────────────────────────────────────
# In dashboard.py, replace:
#   ref_rates = make_mock_ref_rates(TODAY)
# With:
#   from loaders.nyfed_loader import load_ref_rates
#   ref_rates = load_ref_rates(TODAY)
