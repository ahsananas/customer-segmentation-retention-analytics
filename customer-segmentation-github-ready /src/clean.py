"""Data-quality checks and cleaning.

Principles
- Fix only what the data itself can justify; otherwise set to missing and flag.
- Never invent financial or activity values (no mean/median imputation).
- Log every rule with the number of rows affected so the process is auditable.

Run:  python -m src.clean
"""
import numpy as np
import pandas as pd
from .config import RAW, CLEAN, REPORTS, SNAPSHOT

PRODUCT_FLAGS = ["has_savings", "has_term_deposit", "has_credit_card", "has_personal_loan",
                 "has_mortgage", "has_investments", "has_insurance"]
REGION_MAP = {"metro": "Metro", "metropolitan": "Metro", "urban": "Urban", "regional": "Regional",
              "rural": "Rural", "rural area": "Rural"}


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    log = []
    df = raw.copy()
    df["dq_flags"] = ""

    def note(step, rule, n, action, why, check_issue=None):
        log.append({"step": len(log) + 1, "check": step, "rule": rule, "rows_affected": int(n), "action": action,
                    "rationale": why, "injected_issue_key": check_issue or ""})

    def flag(mask, text):
        df.loc[mask, "dq_flags"] = np.where(df.loc[mask, "dq_flags"] == "", text, df.loc[mask, "dq_flags"] + "; " + text)

    n0 = len(df)
    # 1 exact duplicates
    dup = df.duplicated(keep="first")
    note("Exact duplicate rows", "All columns identical", dup.sum(), "Removed (first kept)",
         "Double-loaded rows would double-count customers and balances.", "exact_duplicate_row")
    df = df[~dup].copy()

    # 2 stale snapshots: same customer_id, keep most recent record_updated_at
    df["record_updated_at"] = pd.to_datetime(df["record_updated_at"])
    df = df.sort_values(["customer_id", "record_updated_at"], ascending=[True, False])
    stale = df.duplicated("customer_id", keep="first")
    note("Re-ingested older snapshots", "Same customer_id appears more than once with different values",
         stale.sum(), "Kept the most recent record_updated_at; older rows removed",
         "A customer has one current state; the newest snapshot is the authoritative one.", "stale_snapshot_reingested")
    df = df[~stale].copy().reset_index(drop=True)

    # 3 categorical standardisation
    r0 = df["region"].copy()
    df["region"] = df["region"].str.strip().str.lower().map(REGION_MAP).fillna(df["region"].str.strip())
    m = r0 != df["region"]; flag(m, "region recoded")
    note("Region coding variants", "e.g. 'metro', 'METRO', 'Metropolitan', 'Rural Area'", m.sum(),
         "Mapped to Metro / Urban / Regional / Rural", "Same meaning, different spelling.", "region_variant_coding")
    e0 = df["employment_type"].copy()
    df["employment_type"] = df["employment_type"].str.strip().str.capitalize()
    df["employment_type"] = df["employment_type"].replace({"Self-employed": "Self-employed", "Business owner": "Business owner",
                                                           "Not employed": "Not employed"})
    m = e0 != df["employment_type"]
    note("Employment text case / whitespace", "Upper-case values with trailing spaces", m.sum(), "Trimmed and re-cased",
         "Prevents one category splitting into two.", "employment_case_whitespace")

    # 4 mixed date formats
    s = df["last_login_date"].fillna("").astype(str)
    dmy = s.str.contains("/")
    parsed = pd.to_datetime(s.where(~dmy), format="%Y-%m-%d", errors="coerce")
    parsed[dmy] = pd.to_datetime(s[dmy], format="%d/%m/%Y", errors="coerce")
    df["last_login_date"] = parsed
    note("Mixed date formats (last_login_date)", "DD/MM/YYYY mixed with ISO YYYY-MM-DD", dmy.sum(),
         "Parsed each format explicitly", "Guessing the format could swap day and month.", "login_date_ddmmyyyy")
    df["last_txn_date"] = pd.to_datetime(df["last_txn_date"], format="%Y-%m-%d")
    fut = df["last_txn_date"] > pd.Timestamp(SNAPSHOT)
    flag(fut, "txn date after snapshot")
    note("Transaction dated after the snapshot", f"last_txn_date > {SNAPSHOT}", fut.sum(),
         "Set to missing (recency unknown); flagged", "A future date is impossible; the true date is unknown.",
         "last_txn_after_snapshot")
    df.loc[fut, "last_txn_date"] = pd.NaT

    # 5 impossible ages / sentinel tenure
    m = (df["age"] < 18) | (df["age"] > 105)
    flag(m, "age invalid")
    note("Impossible age", "age < 18 or > 105 (values 0, 150, 999)", m.sum(), "Set to missing",
         "Looks like sentinel / keying values; true age unknown. Age is not used in the segmentation.", "age_sentinel_or_impossible")
    df.loc[m, "age"] = np.nan
    m = df["tenure_months"] < 0
    flag(m, "tenure unknown")
    note("Sentinel tenure", "tenure_months = -1", m.sum(), "Set to missing; loyalty score uses observed components only",
         "-1 is a system placeholder for 'unknown'.", "tenure_sentinel_minus_one")
    df.loc[m, "tenure_months"] = np.nan

    # 6 income
    m_unit = (df["annual_income"] < 1000) & (df["employment_type"] != "Student")
    flag(m_unit, "income x1000 unit fix")
    note("Income recorded in thousands", "annual_income < 1,000 for a non-student (e.g. 54.3)", m_unit.sum(),
         "Multiplied by 1,000", "Values are plausible incomes once read as thousands; no annual income below USD 1,000 "
         "is credible for an earning adult. Income is descriptive only (not in the score).", "income_recorded_in_thousands")
    df.loc[m_unit, "annual_income"] = df.loc[m_unit, "annual_income"] * 1000
    m = df["annual_income"].isna()
    note("Income missing", "annual_income blank", m.sum(), "Left missing (not imputed)",
         "Income is not used in the segmentation, so no estimate is needed.", "income_missing")

    # 7 card fields
    m = df["card_utilisation_pct"] > 150
    flag(m, "card utilisation invalid")
    note("Impossible card utilisation", "card_utilisation_pct > 150%", m.sum(), "Set to missing",
         "Small over-limit use is possible; 160–900% is not.", "card_utilisation_impossible")
    df.loc[m, "card_utilisation_pct"] = np.nan
    m = (df["has_credit_card"] == 1) & df["credit_card_limit"].isna()
    flag(m, "card limit missing")
    note("Card holder without a limit", "has_credit_card = 1 and credit_card_limit blank", m.sum(),
         "Left missing; revolving-balance revenue scored as 0 for these rows and flagged",
         "Limit unknown – no value is invented.", "card_limit_missing")

    # 8 product count
    calc = 1 + df[PRODUCT_FLAGS].sum(axis=1)
    m = calc != df["num_products"]
    flag(m, "num_products recalculated")
    note("Stale product count", "num_products differs from 1 + product flags", m.sum(),
         "Recalculated from the product flags", "Flags are the system of record; the count field is derived.", "num_products_stale")
    df["num_products"] = calc

    # 9 negative savings balances
    m = df["savings_balance"] < 0
    no_prod = m & (df["has_savings"] == 0)
    with_prod = m & (df["has_savings"] == 1)
    flag(m, "savings balance invalid")
    note("Negative savings balance", "savings_balance < 0", m.sum(),
         f"{int(no_prod.sum())} rows with no savings product set to 0; {int(with_prod.sum())} rows with a savings product set to missing",
         "Savings accounts cannot be negative. With no product the balance must be 0; otherwise the true value is unknown.",
         "savings_balance_negative")
    df.loc[no_prod, "savings_balance"] = 0.0
    df.loc[with_prod, "savings_balance"] = np.nan

    # derived recency fields
    snap = pd.Timestamp(SNAPSHOT)
    df["days_since_txn"] = (snap - df["last_txn_date"]).dt.days
    df["days_since_login"] = (snap - df["last_login_date"]).dt.days

    note("Row count reconciliation", f"{n0:,} raw rows → {len(df):,} customers", n0 - len(df),
         "Removed rows = exact duplicates + stale snapshots", "Every customer_id is now unique.")
    df["record_updated_at"] = df["record_updated_at"].dt.strftime("%Y-%m-%d")
    for c in ("last_txn_date", "last_login_date"):
        df[c] = df[c].dt.strftime("%Y-%m-%d")
    return df.sort_values("customer_id").reset_index(drop=True), pd.DataFrame(log)


if __name__ == "__main__":
    raw = pd.read_csv(RAW)
    df, log = clean(raw)
    CLEAN.parent.mkdir(parents=True, exist_ok=True); REPORTS.mkdir(exist_ok=True)
    df.to_csv(CLEAN, index=False)
    log.to_csv(REPORTS / "data_quality_log.csv", index=False)
    print(log[["step", "check", "rows_affected"]].to_string(index=False))
    print("clean customers:", len(df), "unique:", df.customer_id.is_unique)
