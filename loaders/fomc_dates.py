# ── loaders/fomc_dates.py ─────────────────────────────────────────────────────
# Hard-coded FOMC meeting end-dates.
# Source: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
# Refresh this file once a year — 8 meetings per year, use the SECOND day
# (the day the decision is announced).
# ─────────────────────────────────────────────────────────────────────────────

from datetime import date

# 2025 FOMC meeting dates (decision day)
FOMC_2025 = [
    date(2025, 1, 29),
    date(2025, 3, 19),
    date(2025, 5, 7),
    date(2025, 6, 18),
    date(2025, 7, 30),
    date(2025, 9, 17),
    date(2025, 10, 29),
    date(2025, 12, 10),
]

# 2026 FOMC meeting dates (decision day)
FOMC_2026 = [
    date(2026, 1, 28),
    date(2026, 3, 18),
    date(2026, 4, 29),
    date(2026, 6, 17),
    date(2026, 7, 29),
    date(2026, 9, 16),
    date(2026, 10, 28),
    date(2026, 12, 9),
]

ALL_FOMC_DATES = sorted(FOMC_2025 + FOMC_2026)


def load_fomc_dates(today: date) -> list[date]:
    """Return upcoming FOMC dates only (today or later)."""
    return [d for d in ALL_FOMC_DATES if d >= today]


# ── USAGE ─────────────────────────────────────────────────────────────────────
# In dashboard.py, replace:
#   fomc_dates = make_mock_fomc_dates(TODAY)
# With:
#   from loaders.fomc_dates import load_fomc_dates
#   fomc_dates = load_fomc_dates(TODAY)
