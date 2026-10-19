"""Unit tests for the cleaning, scoring and segmentation logic (run: python -m pytest -q)."""
import numpy as np
import pandas as pd
import pytest
from src.clean import clean
from src.features import add_value, add_rei
from src.segment import segment, assign
from src.config import SNAPSHOT, SEGMENT_RULES


def base_row(**kw):
    r = dict(customer_id="CX1", record_updated_at="2026-09-30", age=40, gender="Female", region="Metro",
             employment_type="Salaried", annual_income=60000, tenure_months=60, onboarding_channel="Digital",
             main_bank_flag="Y", has_savings=1, has_term_deposit=0, has_credit_card=1, has_personal_loan=0,
             has_mortgage=0, has_investments=0, has_insurance=0, num_products=3, current_account_avg_bal_3m=4000.0,
             savings_balance=10000.0, term_deposit_balance=0.0, investment_balance=0.0, mortgage_balance=0.0,
             personal_loan_balance=0.0, credit_card_limit=10000.0, card_utilisation_pct=30.0, deposits_6m_ago=14000.0,
             txn_count_90d=40, txn_value_90d=2000.0, card_spend_90d=500.0, last_txn_date="2026-09-28",
             app_registered="Y", app_logins_30d=10, last_login_date="2026-09-29", digital_txn_share=0.8,
             complaints_12m=0, nps_score=8.0, contact_preference="Email", attrited_next_6m=0)
    r.update(kw)
    return r


def test_duplicates_and_stale_snapshot_removed():
    rows = [base_row(), base_row(), base_row(record_updated_at="2026-07-01", current_account_avg_bal_3m=1.0)]
    out, log = clean(pd.DataFrame(rows))
    assert len(out) == 1 and out.loc[0, "current_account_avg_bal_3m"] == 4000.0


def test_no_imputation_of_missing_income():
    out, _ = clean(pd.DataFrame([base_row(annual_income=np.nan)]))
    assert out.annual_income.isna().all()


def test_income_unit_fix_and_mixed_dates():
    out, _ = clean(pd.DataFrame([base_row(annual_income=54.3, last_login_date="29/09/2026")]))
    assert out.annual_income.iloc[0] == pytest.approx(54300)
    assert out.last_login_date.iloc[0] == "2026-09-29"


def test_future_transaction_date_becomes_unknown():
    out, _ = clean(pd.DataFrame([base_row(last_txn_date="2026-10-15")]))
    assert out.days_since_txn.isna().all()
    scored = add_rei(add_value(out))
    assert scored.rei_basis.iloc[0].startswith("Recency unknown") and 0 <= scored.rei.iloc[0] <= 100


def test_product_count_recalculated():
    out, _ = clean(pd.DataFrame([base_row(num_products=7)]))
    assert out.num_products.iloc[0] == 3


def test_rei_bounds_and_recency_decay():
    out, _ = clean(pd.DataFrame([base_row(customer_id="A", last_txn_date="2026-09-30"),
                                 base_row(customer_id="B", last_txn_date="2026-08-31")]))
    s = add_rei(add_value(out)).set_index("customer_id")
    assert s.loc["A", "rei_recency"] == pytest.approx(30)
    assert s.loc["B", "rei_recency"] == pytest.approx(15)          # one half-life (30 days)
    assert s.rei.between(0, 100).all()


def test_bands_use_unrounded_index():
    d = pd.DataFrame({"est_annual_revenue": [500.0], "rei": [69.9976]})
    s, v, e = assign(d)          # 69.9976 must NOT be rounded up into the High band (cut-off 70)
    assert (v[0], e[0]) == ("Mid", "Mid") and s.iloc[0] == "Established Core"


def test_segment_rule_table_is_complete():
    assert len(SEGMENT_RULES) == 9
    d = pd.DataFrame({"est_annual_revenue": [2000, 2000, 2000, 100, 100], "rei": [80, 55, 10, 80, 10]})
    s, _, _ = assign(d)
    assert list(s) == ["Premier Advocates", "Established Core", "Affluent Drifters", "Engaged Builders", "Dormant & Low Value"]
