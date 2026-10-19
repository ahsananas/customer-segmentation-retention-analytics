"""Central configuration: paths, snapshot date and every model assumption in one place.

All values are illustrative assumptions for a SYNTHETIC retail-banking portfolio.
"""
from pathlib import Path
import datetime as dt

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "customers_raw.csv"
CLEAN = ROOT / "data" / "processed" / "customers_clean.csv"
SCORED = ROOT / "data" / "processed" / "customers_scored.csv"
REPORTS = ROOT / "reports"

SEED = 20261019
N_CUSTOMERS = 4000
SNAPSHOT = dt.date(2026, 9, 30)          # "as-of" date for every recency field
CURRENCY = "USD"

# ---------------------------------------------------------------------------
# Revenue proxy assumptions (annual, illustrative – not any real bank's pricing)
# ---------------------------------------------------------------------------
REVENUE_ASSUMPTIONS = {
    "current_account_margin": 0.025,   # funding benefit on current-account balances
    "savings_margin": 0.012,           # net interest margin on savings
    "term_deposit_margin": 0.008,      # thinner margin on term deposits
    "investment_fee": 0.0075,          # annual platform / advisory fee on investments
    "mortgage_margin": 0.011,          # net interest margin on mortgage balances
    "personal_loan_margin": 0.045,     # net interest margin on personal loans
    "card_revolve_margin": 0.12,       # margin on revolving card balance
    "card_interchange": 0.012,         # interchange on card spend
}

# ---------------------------------------------------------------------------
# Segmentation – two axes
#   Value axis      : estimated annual revenue (USD), fixed bands
#   Engagement axis : 0–100 Relationship Engagement Index (REI)
# ---------------------------------------------------------------------------
REI_WEIGHTS = {            # sum = 100
    "recency": 30,         # how recently the customer transacted
    "frequency": 20,       # how often (90-day transaction count)
    "digital": 15,         # app logins + share of transactions done digitally
    "adoption": 20,        # product breadth beyond the current account
    "loyalty": 15,         # tenure, main-bank status, complaint-free service
}
RECENCY_HALF_LIFE_DAYS = 30       # recency points halve every 30 days without a transaction
FREQUENCY_CAP = 120               # 90-day transactions at which frequency points max out
LOGIN_CAP = 20                    # 30-day app logins at which login points max out
ADOPTION_CAP = 4                  # products beyond the current account at which adoption maxes out
TENURE_CAP_YEARS = 10

VALUE_BANDS = {"High": 1500, "Mid": 400}   # USD est. annual revenue: High >= 1,500; Mid 400–1,499; Low < 400
ENGAGEMENT_BANDS = {"High": 70, "Mid": 50}  # REI: High >= 70; Mid 50–69.9; Low < 50

SEGMENTS = [   # display order
    "Premier Advocates", "Established Core", "Affluent Drifters", "Engaged Builders", "Light Touch", "Dormant & Low Value",
]
SEGMENT_RULES = {  # (value band, engagement band) -> segment
    ("High", "High"): "Premier Advocates",
    ("High", "Mid"): "Established Core",
    ("Mid", "Mid"): "Established Core",
    ("High", "Low"): "Affluent Drifters",
    ("Mid", "High"): "Engaged Builders",
    ("Low", "High"): "Engaged Builders",
    ("Mid", "Low"): "Light Touch",
    ("Low", "Mid"): "Light Touch",
    ("Low", "Low"): "Dormant & Low Value",
}
