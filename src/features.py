"""Feature engineering: relationship value (revenue proxy) and the Relationship Engagement Index (REI).

Every formula is deliberately simple so it can be rebuilt in a spreadsheet (see workbook/).
"""
import numpy as np
import pandas as pd
from .config import (REVENUE_ASSUMPTIONS as RA, REI_WEIGHTS as W, RECENCY_HALF_LIFE_DAYS, FREQUENCY_CAP,
                     LOGIN_CAP, ADOPTION_CAP, TENURE_CAP_YEARS)

CARD_REVOLVING_SHARE = 0.5   # assumption: half of the utilised card balance revolves (pays interest)


def add_value(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["total_deposits"] = d[["current_account_avg_bal_3m", "savings_balance", "term_deposit_balance"]].sum(axis=1, min_count=1)
    d["card_balance"] = (d["credit_card_limit"] * d["card_utilisation_pct"] / 100)
    d["total_lending"] = d[["mortgage_balance", "personal_loan_balance", "card_balance"]].sum(axis=1)
    comp = pd.DataFrame(index=d.index)
    comp["rev_current_account"] = d["current_account_avg_bal_3m"] * RA["current_account_margin"]
    comp["rev_savings"] = d["savings_balance"] * RA["savings_margin"]
    comp["rev_term_deposit"] = d["term_deposit_balance"] * RA["term_deposit_margin"]
    comp["rev_investments"] = d["investment_balance"] * RA["investment_fee"]
    comp["rev_mortgage"] = d["mortgage_balance"] * RA["mortgage_margin"]
    comp["rev_personal_loan"] = d["personal_loan_balance"] * RA["personal_loan_margin"]
    comp["rev_card_revolve"] = d["card_balance"] * CARD_REVOLVING_SHARE * RA["card_revolve_margin"]
    comp["rev_card_interchange"] = d["card_spend_90d"] * 4 * RA["card_interchange"]
    d = pd.concat([d, comp], axis=1)
    # full precision is kept: rounding before banding could move a customer across a cut-off (display rounding happens in outputs)
    d["est_annual_revenue"] = comp.sum(axis=1, min_count=1)   # unknown components contribute nothing
    # a component is "unknown" only where the customer holds the product but the input is missing
    unknown = (d["has_savings"].eq(1) & d["savings_balance"].isna()) | \
              (d["has_credit_card"].eq(1) & (d["credit_card_limit"].isna() | d["card_utilisation_pct"].isna()))
    d["value_basis"] = np.where(unknown, "Partial – a balance input is missing", "All inputs available")
    d["deposit_change_6m_pct"] = ((d["total_deposits"] / d["deposits_6m_ago"] - 1) * 100).round(1)
    return d


def rei_components(d: pd.DataFrame) -> pd.DataFrame:
    c = pd.DataFrame(index=d.index)
    c["rei_recency"] = W["recency"] * np.power(0.5, d["days_since_txn"] / RECENCY_HALF_LIFE_DAYS)
    c["rei_frequency"] = W["frequency"] * np.minimum(1, np.log1p(d["txn_count_90d"]) / np.log1p(FREQUENCY_CAP))
    c["rei_digital"] = W["digital"] * (0.6 * np.minimum(1, d["app_logins_30d"] / LOGIN_CAP) + 0.4 * d["digital_txn_share"].fillna(0))
    c["rei_adoption"] = W["adoption"] * np.minimum(1, (d["num_products"] - 1) / ADOPTION_CAP)
    ten = np.minimum(1, d["tenure_months"] / 12 / TENURE_CAP_YEARS)
    mb = (d["main_bank_flag"] == "Y").astype(float)
    svc = 1 - np.minimum(d["complaints_12m"], 3) / 3
    # loyalty: tenure 40%, main bank 35%, complaint-free 25%; unknown tenure -> scored on the other two
    lw = np.where(ten.isna(), 0.60, 1.0)
    c["rei_loyalty"] = W["loyalty"] * (0.40 * ten.fillna(0) + 0.35 * mb + 0.25 * svc) / lw
    return c


def add_rei(df: pd.DataFrame, weights: dict | None = None) -> pd.DataFrame:
    """REI = sum of components (0–100). Recency unknown (date invalid) -> index rescaled over observed components."""
    d = df.copy()
    c = rei_components(d)
    if weights:  # sensitivity: rescale each component to its alternative weight
        for k, w in weights.items():
            c[f"rei_{k}"] = c[f"rei_{k}"] / W[k] * w if W[k] else 0
        wts = weights
    else:
        wts = W
    observed_max = sum(wts.values()) - np.where(c["rei_recency"].isna(), wts["recency"], 0)
    d[c.columns] = c
    d["rei"] = c.sum(axis=1, min_count=1) / observed_max * 100   # full precision; bands use the unrounded index
    d["rei_basis"] = np.where(c["rei_recency"].isna(), "Recency unknown – scored on other components", "All components")
    return d
