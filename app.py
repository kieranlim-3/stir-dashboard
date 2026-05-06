# ── app.py · STIR Dashboard · Streamlit ──────────────────────────────────────
# Run locally:  streamlit run app.py
# Deploy:       Push to GitHub → connect on share.streamlit.io
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="US STIR Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Brand palette ─────────────────────────────────────────────────────────────
CFR = {
    "bg":        "#000000",
    "panel":     "#080808",
    "orange":    "#FE7C04",
    "orangeHot": "#FF9533",
    "orangeDim": "#5A2C00",
    "text":      "#D0D0D0",
}

# ── CME helpers ───────────────────────────────────────────────────────────────
_CME_MONTH_CODES = {
    1:"F", 2:"G",  3:"H", 4:"J",  5:"K", 6:"M",
    7:"N", 8:"Q",  9:"U", 10:"V", 11:"X", 12:"Z"
}

def _cme_symbol(root: str, expiry: date) -> str:
    return f"{root}{_CME_MONTH_CODES[expiry.month]}{expiry.year % 10}"

@dataclass
class Contract:
    symbol: str
    root:   str
    expiry: date
    settle: float

def to_strip(contracts: list[Contract]) -> pd.DataFrame:
    return pd.DataFrame([c.__dict__ for c in contracts])


# ── Synthetic data (replace with real loaders) ────────────────────────────────
@st.cache_data(ttl=3600)
def load_strip(today: date) -> pd.DataFrame:
    np.random.seed(42)
    contracts: list[Contract] = []
    sr3_months = [
        (today.year + (today.month + i * 3 - 1) // 12,
         ((today.month - 1 + i * 3) % 12) + 1)
        for i in range(8)
    ]
    sr3_rates = [4.20, 4.05, 3.92, 3.75, 3.55, 3.42, 3.50, 3.62]
    for (y, m), r in zip(sr3_months, sr3_rates):
        qm  = next(q for q in (3, 6, 9, 12) if q >= m) if m not in (3,6,9,12) else m
        exp = date(y, qm, monthrange(y, qm)[1])
        contracts.append(Contract(_cme_symbol("SR3", exp), "SR3", exp, 100.0 - r))
    rng = np.linspace(4.30, 3.30, 18) + np.random.normal(0, 0.015, 18)
    for i, r in enumerate(rng):
        m   = ((today.month - 1 + i) % 12) + 1
        y   = today.year + (today.month + i - 1) // 12
        exp = date(y, m, monthrange(y, m)[1])
        contracts.append(Contract(_cme_symbol("ZQ", exp), "ZQ", exp, 100.0 - r))
    return to_strip(contracts).sort_values(["root","expiry"]).reset_index(drop=True)

@st.cache_data(ttl=3600)
def load_ref_rates(today: date) -> pd.DataFrame:
    from loaders.nyfed_loader import load_ref_rates as _load
    return _load(today)

def load_fomc_dates(today: date) -> list[date]:
    all_dates = [
        date(2025,1,29), date(2025,3,19), date(2025,5,7),  date(2025,6,18),
        date(2025,7,30), date(2025,9,17), date(2025,10,29),date(2025,12,10),
        date(2026,1,28), date(2026,3,18), date(2026,4,29), date(2026,6,17),
        date(2026,7,29), date(2026,9,16), date(2026,10,28),date(2026,12,9),
    ]
    return [d for d in all_dates if d >= today]


# ── Core compute ──────────────────────────────────────────────────────────────
def add_implied(strip: pd.DataFrame, ocr: float) -> pd.DataFrame:
    out = strip.copy()
    out["implied_rate"] = 100.0 - out["settle"]
    out["vs_ocr_bp"]    = (out["implied_rate"] - ocr) * 100.0
    return out

def find_terminal(strip_view: pd.DataFrame, ocr: float) -> pd.Series:
    active = strip_view[strip_view["settle"] > 0].reset_index(drop=True)
    if active.empty:
        return strip_view.iloc[0]
    front  = active.iloc[0]
    hiking = front["implied_rate"] >= ocr
    best   = front
    for _, row in active.iloc[1:].iterrows():
        if hiking and row["implied_rate"] >= best["implied_rate"]:
            best = row
        elif not hiking and row["implied_rate"] <= best["implied_rate"]:
            best = row
        else:
            break
    return best

def post_meeting_rate(contract_rate, prev_rate, meeting_day, days_in_month):
    days_after = days_in_month - meeting_day + 1
    if days_after <= 0:
        return contract_rate
    return (contract_rate * days_in_month - (meeting_day - 1) * prev_rate) / days_after

def build_meeting_path(zq_strip, effr_today, fomc_dates):
    zq_by_month = {(r["expiry"].year, r["expiry"].month): r["implied_rate"]
                   for _, r in zq_strip.iterrows()}
    fomc_keys   = {(d.year, d.month) for d in fomc_dates}
    prev, rows  = effr_today, []
    for d in fomc_dates:
        rate = zq_by_month.get((d.year, d.month))
        if rate is None:
            continue
        N  = monthrange(d.year, d.month)[1]
        ny = d.year + (d.month == 12)
        nm = d.month % 12 + 1
        next_rate        = zq_by_month.get((ny, nm))
        next_has_meeting = (ny, nm) in fomc_keys
        post = next_rate if (next_rate is not None and not next_has_meeting) \
               else post_meeting_rate(rate, prev, d.day, N)
        rows.append({"meeting": d, "post_rate": post,
                     "cum_cuts": (effr_today - post) / 0.25})
        prev = post
    return pd.DataFrame(rows)

def meeting_probs(post_rate, effr):
    raw   = (effr - post_rate) / 0.25
    lower = int(np.floor(raw))
    frac  = raw - lower
    mass  = {lower: 1 - frac}
    if frac > 0.001:
        mass[lower + 1] = frac
    return {"hold":   100 * mass.get(0,  0.0),
            "cut25":  100 * mass.get(1,  0.0),
            "cut50":  100 * mass.get(2,  0.0),
            "cut75":  100 * mass.get(3,  0.0),
            "hike25": 100 * mass.get(-1, 0.0)}

def spread_matrix(strip_view, horizons_m=(3, 6, 9, 12)):
    if strip_view.empty:
        return pd.DataFrame()
    rows = []
    for _, row in strip_view.iterrows():
        row_mo  = row["expiry"].month + 12 * row["expiry"].year
        spreads = {}
        for h in horizons_m:
            fwd = strip_view[strip_view["expiry"].apply(
                lambda d: d.month + 12 * d.year >= row_mo + h)]
            spreads[f"+{h}M"] = (round((fwd.iloc[0]["implied_rate"]
                                        - row["implied_rate"]) * 100)
                                  if not fwd.empty else float("nan"))
        rows.append({"contract": row["symbol"], **spreads})
    return pd.DataFrame(rows).set_index("contract")

def cb_levels(effr, band_bp=150, step_bp=25):
    settle = round(effr / 0.25) * 0.25
    n = band_bp // step_bp
    return [settle + (i - n) * (step_bp / 100.0) for i in range(2 * n + 1)]


# ── Plotly builders ───────────────────────────────────────────────────────────
def make_strip_fig(strip_view, ocr, title):
    term   = find_terminal(strip_view, ocr)
    colors = [CFR["orangeHot"] if s == term["symbol"] else CFR["orangeDim"]
              for s in strip_view["symbol"]]
    fig = go.Figure(go.Bar(
        x=strip_view["symbol"], y=strip_view["implied_rate"],
        marker_color=colors, marker_line_color="#9A4A02",
        hovertemplate="%{x}<br>%{y:.3f}%<extra></extra>",
    ))
    fig.add_hline(y=ocr, line_dash="dash", line_color=CFR["orange"],
                  annotation_text="EFFECTIVE FFR", annotation_position="right",
                  annotation_font=dict(color=CFR["orange"]))
    fig.update_layout(
        title=dict(text=title, font=dict(color=CFR["orange"], size=16)),
        template="plotly_dark", paper_bgcolor=CFR["bg"], plot_bgcolor="#050505",
        font=dict(color=CFR["text"]), yaxis_title="Implied rate (%)",
        margin=dict(l=60, r=20, t=50, b=40), height=400,
    )
    return fig

def make_path_fig(path, effr, cb=False):
    fig = go.Figure(go.Scatter(
        x=path["meeting"], y=path["post_rate"],
        mode="lines+markers",
        line=dict(color=CFR["orangeHot"], width=2.4, shape="hv"),
        marker=dict(color=CFR["bg"],
                    line=dict(color=CFR["orangeHot"], width=1.5), size=8),
        hovertemplate="%{x|%b %Y}<br>%{y:.3f}%<extra></extra>",
    ))
    fig.add_hline(y=effr, line_dash="dash", line_color=CFR["orange"],
                  annotation_text="EFFECTIVE FFR", annotation_position="right",
                  annotation_font=dict(color=CFR["orange"]))
    if cb:
        settle = round(effr / 0.25) * 0.25
        for lv in cb_levels(effr):
            is_s = abs(lv - settle) < 0.01
            fig.add_hline(
                y=lv,
                line_color=CFR["orange"] if is_s else CFR["orangeDim"],
                line_dash="solid" if is_s else "dot",
                line_width=1.4    if is_s else 0.6,
                annotation_text=f"{lv:.2f}%" + (" · SETTLE" if is_s else ""),
                annotation_position="right",
                annotation_font=dict(
                    color=CFR["orange"] if is_s else CFR["orangeDim"], size=9),
            )
    fig.update_layout(
        template="plotly_dark", paper_bgcolor=CFR["bg"], plot_bgcolor="#050505",
        font=dict(color=CFR["text"]), yaxis_title="Implied post-meeting rate (%)",
        margin=dict(l=60, r=80, t=30, b=40), height=420,
    )
    return fig


# ── App layout ────────────────────────────────────────────────────────────────
TODAY = date.today()

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    h1 { color: #FE7C04 !important; }
    .stTabs [data-baseweb="tab"] { color: #D0D0D0; }
    .stTabs [aria-selected="true"] { color: #FE7C04 !important; }
    .metric-box {
        background: #080808; border: 1px solid #3D2510;
        border-radius: 6px; padding: 12px 20px; text-align: center;
    }
    .metric-label { color: #888; font-size: 0.75rem; letter-spacing: 0.08em; }
    .metric-value { color: #FE7C04; font-size: 1.6rem; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

st.title("US STIR Dashboard")
st.caption("CME FedWatch-style rate expectations · Synthetic data (swap loaders for live feed)")

# Load data
strip      = load_strip(TODAY)
ref_rates  = load_ref_rates(TODAY)
fomc_dates = load_fomc_dates(TODAY)

OCR  = float(ref_rates["effr"].iloc[-1])
SOFR = float(ref_rates["sofr"].iloc[-1])

strip      = add_implied(strip, OCR)
sofr_strip = strip[strip["root"] == "SR3"].reset_index(drop=True)
ff_strip   = strip[strip["root"] == "ZQ"].reset_index(drop=True)
path       = build_meeting_path(ff_strip, OCR, fomc_dates)

# ── Top metrics row ───────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f"""<div class="metric-box">
        <div class="metric-label">EFFECTIVE FFR</div>
        <div class="metric-value">{OCR:.2f}%</div>
    </div>""", unsafe_allow_html=True)
with c2:
    st.markdown(f"""<div class="metric-box">
        <div class="metric-label">SOFR SPOT</div>
        <div class="metric-value">{SOFR:.2f}%</div>
    </div>""", unsafe_allow_html=True)
with c3:
    basis = (SOFR - OCR) * 100
    st.markdown(f"""<div class="metric-box">
        <div class="metric-label">SOFR / EFFR BASIS</div>
        <div class="metric-value">{basis:+.1f} bp</div>
    </div>""", unsafe_allow_html=True)
with c4:
    terminal_cuts = path["cum_cuts"].iloc[-1] if not path.empty else 0
    st.markdown(f"""<div class="metric-box">
        <div class="metric-label">CUTS PRICED (TERMINAL)</div>
        <div class="metric-value">{terminal_cuts:.1f}x 25bp</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["PRODUCTS", "MEETINGS"])

with tab1:
    product = st.radio("Product", ["SOFR (SR3)", "Fed Funds (ZQ)"],
                       horizontal=True, label_visibility="collapsed")
    if product == "SOFR (SR3)":
        st.plotly_chart(make_strip_fig(sofr_strip, OCR, "SOFR · 3-Month Futures Strip"),
                        width="stretch")
    else:
        st.plotly_chart(make_strip_fig(ff_strip, OCR, "Fed Funds · 30-Day Futures Strip"),
                        width="stretch")

with tab2:
    sub = st.radio("View", ["STRIP", "SPREADS", "CB LVL"],
                   horizontal=True, label_visibility="collapsed")

    if sub == "STRIP":
        st.plotly_chart(make_path_fig(path, OCR), width="stretch")
        st.markdown("**Meeting Probabilities (%)**")
        probs_df = pd.DataFrame(
            [meeting_probs(r, OCR) for r in path["post_rate"]],
            index=[d.strftime("%b %Y") for d in path["meeting"]],
        ).round(1)
        probs_df.columns = ["Hold", "Cut 25", "Cut 50", "Cut 75", "Hike 25"]
        st.dataframe(probs_df, width="stretch")

    elif sub == "SPREADS":
        st.markdown("**Calendar Spread Matrix (bp)**")
        sm = spread_matrix(ff_strip)
        st.dataframe(sm.style.background_gradient(cmap="RdYlGn", axis=None),
                     width="stretch")

    else:  # CB LVL
        st.plotly_chart(make_path_fig(path, OCR, cb=True), width="stretch")

st.markdown("---")
st.caption("Data: Synthetic · Methodology: Capital Flows Research STIR Replication Playbook · Built with Streamlit + Plotly")
