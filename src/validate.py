"""Independent validation of the pipeline outputs. Writes docs/VALIDATION.md and reports/validation_checks.csv.

Run after src.run_all:   python -m src.validate
"""
import hashlib, json
import numpy as np
import pandas as pd
from .config import RAW, CLEAN, SCORED, REPORTS, ROOT, SNAPSHOT, SEGMENT_RULES, VALUE_BANDS, ENGAGEMENT_BANDS, REVENUE_ASSUMPTIONS as RA
from . import generate_data
from .features import CARD_REVOLVING_SHARE
from .retention import MODEL_FEATURES

R = []


def check(area, name, ok, detail=""):
    R.append({"area": area, "check": name, "result": "PASS" if bool(ok) else "FAIL", "detail": str(detail)})


def main():
    raw = pd.read_csv(RAW); clean = pd.read_csv(CLEAN); d = pd.read_csv(SCORED)
    man = pd.read_csv(RAW.parent / "injected_issues_manifest.csv"); dq = pd.read_csv(REPORTS / "data_quality_log.csv")
    S = json.load(open(REPORTS / "summary.json"))

    # ---- reproducibility
    h1 = hashlib.sha256(open(RAW, "rb").read()).hexdigest()
    generate_data.rng = np.random.default_rng(generate_data.SEED)
    r2, _, _ = generate_data.generate()
    h2 = hashlib.sha256(r2.drop(columns=["source_row_type"]).to_csv(index=False).encode()).hexdigest()
    check("Reproducibility", "Regenerating with the same seed gives a byte-identical raw file", h1 == h2, h1[:12])

    # ---- row accounting
    n_dup = int((man.issue == "exact_duplicate_row").sum()); n_stale = int((man.issue == "stale_snapshot_reingested").sum())
    check("Rows", "Raw rows = customers + exact duplicates + stale snapshots", len(raw) == len(clean) + n_dup + n_stale,
          f"{len(raw):,} = {len(clean):,} + {n_dup} + {n_stale}")
    check("Rows", "One row per customer after cleaning", clean.customer_id.is_unique and len(clean) == 4000, f"{len(clean):,}")
    check("Rows", "Scored file has every cleaned customer", len(d) == len(clean) and set(d.customer_id) == set(clean.customer_id))

    # ---- detection vs injected ground truth
    det = dict(zip(dq.injected_issue_key.fillna(""), dq.rows_affected))
    for key, n in man.issue.value_counts().items():
        got = int(det.get(key, -1))
        detail = f"injected {n}, detected {got}"
        ok = got == n
        if key == "income_recorded_in_thousands" and got != n:
            ids = man.loc[man.issue == key, "customer_id"]
            overwritten = int(man[(man.issue == "income_missing") & man.customer_id.isin(ids)].shape[0])
            ok = got == n - overwritten
            detail += f" ({overwritten} of these rows were later blanked by the 'income missing' injection, so cannot be detected)"
        check("Cleaning vs ground truth", key, ok, detail)

    # ---- integrity of the cleaned data
    num = ["current_account_avg_bal_3m", "savings_balance", "term_deposit_balance", "investment_balance", "mortgage_balance",
           "personal_loan_balance", "credit_card_limit"]
    check("Integrity", "No negative balances remain", (clean[num].fillna(0) >= 0).all().all())
    check("Integrity", "Ages are 18–105 or missing", clean.age.dropna().between(18, 105).all())
    _dt = pd.to_datetime(clean.last_txn_date)
    check("Integrity", "No dates after the snapshot", (_dt.isna() | (_dt <= pd.Timestamp(SNAPSHOT))).all(), f"{int(_dt.isna().sum())} unknown (were future-dated)")
    flags = ["has_savings", "has_term_deposit", "has_credit_card", "has_personal_loan", "has_mortgage", "has_investments", "has_insurance"]
    check("Integrity", "num_products = 1 + product flags", (clean.num_products == 1 + clean[flags].sum(axis=1)).all())
    check("Integrity", "Card utilisation ≤ 150% or missing", clean.card_utilisation_pct.dropna().le(150).all())
    check("Integrity", "Categories standardised", set(clean.region) == {"Metro", "Urban", "Regional", "Rural"},
          ", ".join(sorted(clean.region.unique())))

    # ---- no invented values: every changed cell is explained by a logged rule
    latest = raw.sort_values("record_updated_at", ascending=False).drop_duplicates("customer_id").set_index("customer_id").sort_index()
    c = clean.set_index("customer_id").sort_index()
    filled = {}
    for col in ["annual_income", "savings_balance", "credit_card_limit", "card_utilisation_pct", "age", "tenure_months", "nps_score"]:
        filled[col] = int((latest[col].isna() & c[col].notna()).sum())
    check("No imputation", "No blank source value was filled in", sum(filled.values()) == 0, filled)
    check("No imputation", "Income still missing where the source was blank", int(c.annual_income.isna().sum()) == int(latest.annual_income.isna().sum()),
          int(c.annual_income.isna().sum()))

    # ---- calculations re-derived independently
    rev = (d.current_account_avg_bal_3m * RA["current_account_margin"] + d.savings_balance.fillna(0) * RA["savings_margin"]
           + d.term_deposit_balance * RA["term_deposit_margin"] + d.investment_balance * RA["investment_fee"]
           + d.mortgage_balance * RA["mortgage_margin"] + d.personal_loan_balance * RA["personal_loan_margin"]
           + (d.credit_card_limit * d.card_utilisation_pct / 100).fillna(0) * CARD_REVOLVING_SHARE * RA["card_revolve_margin"]
           + d.card_spend_90d * 4 * RA["card_interchange"])
    check("Calculations", "Revenue proxy re-derived from raw inputs", np.allclose(rev, d.est_annual_revenue, atol=0.05),
          f"max diff {abs(rev - d.est_annual_revenue).max():.3f}")
    check("Calculations", "REI within 0–100", d.rei.between(0, 100).all(), f"{d.rei.min():.1f}–{d.rei.max():.1f}")
    vb = np.select([d.est_annual_revenue >= VALUE_BANDS["High"], d.est_annual_revenue >= VALUE_BANDS["Mid"]], ["High", "Mid"], "Low")
    eb = np.select([d.rei >= ENGAGEMENT_BANDS["High"], d.rei >= ENGAGEMENT_BANDS["Mid"]], ["High", "Mid"], "Low")
    check("Calculations", "Every segment matches the published rule table", (pd.Series([SEGMENT_RULES[(a, b)] for a, b in zip(vb, eb)]) == d.segment).all())
    sg = pd.DataFrame(S["segments"])
    check("Calculations", "Segment counts sum to customers", int(sg.customers.sum()) == len(d), int(sg.customers.sum()))
    check("Calculations", "Segment revenue reconciles to portfolio total", abs(sg.revenue.sum() - d.est_annual_revenue.sum()) < 1,
          f"USD {d.est_annual_revenue.sum():,.0f}")
    check("Calculations", "Revenue shares sum to 100%", abs(sg.revenue_share_pct.sum() - 100) < 0.05)

    # ---- model hygiene
    check("Model", "Outcome is not used as a feature", "attrited_next_6m" not in MODEL_FEATURES and all(c["feature"] in MODEL_FEATURES for c in S["coefficients"]), ", ".join(MODEL_FEATURES))
    check("Model", "Test AUC reported on held-out 30%", S["model"]["n_test"] > 1000, f"AUC {S['model']['auc_test']} on {S['model']['n_test']} customers")
    check("Model", "Records with a missing model input are not scored", int(d.attrition_risk_model.isna().sum()) == S["model"]["not_scored_missing_input"],
          S["model"]["not_scored_missing_input"])

    # ---- robustness
    sw = pd.DataFrame(S["sensitivity"])
    check("Sensitivity", "All alternative weightings keep ≥ 80% of customers in the same segment",
          sw[sw.test == "REI weights"].same_segment_pct.min() >= 80, f"min {sw[sw.test == 'REI weights'].same_segment_pct.min()}%")

    # ---- workbook (if built)
    wb = ROOT / "workbook" / "segmentation_workings.xlsx"
    if wb.exists():
        x = pd.read_excel(wb, sheet_name="Scoring", header=3)
        x = x.set_index("customer_id").loc[d.customer_id]
        check("Workbook", "Excel revenue formulas = Python", np.allclose(x["est_annual_revenue"].values, d.est_annual_revenue.values, atol=0.05))
        check("Workbook", "Excel REI formulas = Python", np.allclose(x["rei"].values, d.rei.values, atol=0.01))
        check("Workbook", "Excel segment formulas = Python", (x["segment"].values == d.segment.values).all())

    out = pd.DataFrame(R); out.to_csv(REPORTS / "validation_checks.csv", index=False)
    md = ["# Validation report", "", f"Generated by `python -m src.validate`. **{(out.result == 'PASS').sum()} of {len(out)} checks passed.**", "",
          "All data is synthetic. These checks confirm the pipeline does what it says; they do not validate real-world behaviour.", "",
          "| Area | Check | Result | Detail |", "|---|---|---|---|"]
    md += [f"| {r.area} | {r.check} | {r.result} | {r.detail} |" for r in out.itertuples()]
    (ROOT / "docs").mkdir(exist_ok=True)
    open(ROOT / "docs" / "VALIDATION.md", "w").write("\n".join(md) + "\n")
    print(out.to_string()); print("FAILED:", (out.result == "FAIL").sum())


if __name__ == "__main__":
    main()
