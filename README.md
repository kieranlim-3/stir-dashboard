# US STIR Dashboard

A CME FedWatch-style Fed Funds rate expectations dashboard built from publicly listed CME futures and NY Fed reference rates. Replicates the methodology used by professional rates desks to extract market-implied FOMC probabilities from fed funds futures prices.

---

## What It Shows

**PRODUCTS tab**
- SOFR (SR3) futures strip — implied 3-month compounded SOFR by contract
- Fed Funds (ZQ) futures strip — implied average EFFR by contract month
- Both plotted against today's Effective Federal Funds Rate (EFFR)

**MEETINGS tab**
- Implied post-meeting rate path extracted from ZQ futures via day-weighting
- FedWatch-style probability distribution (P(hold) / P(cut 25) / P(cut 50) / etc.)
- Calendar spread matrix (+3M / +6M / +9M / +12M)
- CB LVL chart — meeting path overlaid with 25 bp policy-rate rails

---

## Methodology

### Implied Rate
Both SR3 and ZQ use the IMM 100-minus-rate convention:

```
implied_rate = 100 - settlement_price
```

A contract settling at 95.42 implies a 4.58% rate for its reference period.

### Day-Weighted Post-Meeting Rate
A 30-day fed funds future settles to the arithmetic average of daily EFFR across its expiry month. If the FOMC meets on day D of an N-day month:

```
monthly_avg = ((D-1) × prevRate + (N-D+1) × postRate) / N
```

Solving for postRate:

```
postRate = (monthly_avg × N - (D-1) × prevRate) / (N - D + 1)
```

Iterated forward through the FOMC calendar — the post-meeting rate at meeting k becomes prevRate for meeting k+1.

### FedWatch Probability Interpolation
From the implied post-meeting rate, recover probability mass across 25 bp policy levels:

```
raw_cuts = (EFFR - postRate) / 0.0025
lower    = floor(raw_cuts)
frac     = raw_cuts - lower

P(lower cuts) = 1 - frac
P(lower+1 cuts) = frac
```

This is the same interpolation CME FedWatch publishes.

---

## Data Inputs

| Input | Source | Cost |
|-------|--------|------|
| EFFR (Effective Fed Funds Rate) | NY Fed CSV | Free |
| SOFR (Secured Overnight Financing Rate) | NY Fed CSV | Free |
| FOMC meeting dates | federalreserve.gov | Free (hard-coded) |
| ZQ settlement prices (30-day Fed Funds futures) | IBKR / Polygon / CME DataMine | Varies |
| SR3 settlement prices (3-month SOFR futures) | IBKR / Polygon / CME DataMine | Varies |

EFFR and SOFR are published daily at [markets.newyorkfed.org](https://markets.newyorkfed.org).

---

## Quickstart

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run on synthetic data (no provider needed)
```bash
python dashboard.py
```

This runs end-to-end on simulated data and opens four Plotly charts.

### 3. Plug in real data
Replace the three mock loaders in `dashboard.py` with real ones:

```python
# EFFR + SOFR — free from NY Fed
from loaders.nyfed_loader import load_ref_rates
ref_rates = load_ref_rates(TODAY)

# FOMC dates — hard-coded, refresh annually
from loaders.fomc_dates import load_fomc_dates
fomc_dates = load_fomc_dates(TODAY)

# ZQ / SR3 settlements — from your provider
# See loaders/ folder for provider-specific templates
strip = your_provider_loader(TODAY)
```

---

## Project Structure

```
stir-dashboard/
├── dashboard.py          # Main file — all methodology + driver
├── requirements.txt
├── loaders/
│   ├── nyfed_loader.py   # Free EFFR + SOFR from NY Fed
│   ├── fomc_dates.py     # Hard-coded FOMC calendar (refresh annually)
│   └── ibkr_loader.py    # ZQ/SR3 via IBKR (template)
└── data/                 # Optional: cache CSVs locally
```

---

## Output

Running `python dashboard.py` produces:

1. **SOFR strip chart** — SR3 contracts with terminal highlighted
2. **Fed Funds strip chart** — ZQ contracts with terminal highlighted
3. **Meeting path chart** — implied post-meeting rate at each FOMC date
4. **CB LVL chart** — meeting path overlaid with 25 bp policy rails
5. **Probability table** (printed) — P(hold/cut25/cut50/cut75/hike25) per meeting
6. **Spread matrix** (printed) — +3M/+6M/+9M/+12M forward spreads in bp

---

## References

- [CME FedWatch Tool](https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html)
- [NY Fed EFFR](https://www.newyorkfed.org/markets/reference-rates/effr)
- [NY Fed SOFR](https://www.newyorkfed.org/markets/reference-rates/sofr)
- [FOMC Meeting Calendar](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm)
- Capital Flows Research · STIR Replication Playbook

---

## Why This Project

Extracting market-implied rate expectations from futures prices is a core skill in rates research, ALM, and quantitative finance. This project demonstrates:

- Understanding of CME futures contract conventions (IMM pricing, day-count)
- Day-weighting math used by professional rates desks
- Clean, modular pipeline architecture (provider → loader → compute → visualise)
- Ability to replicate institutional-grade tooling from first principles
