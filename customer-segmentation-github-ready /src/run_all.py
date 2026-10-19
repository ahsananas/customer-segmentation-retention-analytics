"""End-to-end pipeline: generate -> clean -> features -> segment -> retention -> insights -> outputs.

Run from the repository root:   python -m src.run_all
Every number used by the dashboard, workbook, slides and README comes from reports/summary.json.
"""
import json
from math import sqrt
import numpy as np
import pandas as pd
from . import generate_data
from .config import RAW, CLEAN, SCORED, REPORTS, SEGMENTS, SNAPSHOT, REVENUE_ASSUMPTIONS, REI_WEIGHTS, VALUE_BANDS, ENGAGEMENT_BANDS
from .clean import clean
from .features import add_value, add_rei, CARD_REVOLVING_SHARE
from .segment import segment, sensitivity, kmeans_check
from .retention import signal_table, add_signal_count, model


# records whose key facts are uncertain are held out of any campaign or pilot
HOLD_PATTERN = "age invalid|txn date after snapshot|savings balance invalid"


def mde(n_per_arm, p0, z=2.80):
    """Smallest absolute difference detectable at 95% confidence / 80% power (two-proportion, equal arms)."""
    return z * sqrt(2 * p0 * (1 - p0) / n_per_arm)


def main():
    REPORTS.mkdir(exist_ok=True)
    # 1 generate (seeded, reproducible)
    raw, truth, manifest = generate_data.generate()
    RAW.parent.mkdir(parents=True, exist_ok=True)
    raw.drop(columns=["source_row_type"]).to_csv(RAW, index=False)
    manifest.drop(columns=["truth_index"]).to_csv(RAW.parent / "injected_issues_manifest.csv", index=False)
    raw = pd.read_csv(RAW)

    # 2 clean
    df, dq = clean(raw)
    CLEAN.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CLEAN, index=False); dq.to_csv(REPORTS / "data_quality_log.csv", index=False)

    # 3 features + 4 segments
    d = segment(add_rei(add_value(df)))
    # 5 retention
    d = add_signal_count(d)
    p, mmetrics, deciles, coef = model(d)
    d["attrition_risk_model"] = p.round(4)
    q90, q70 = d["attrition_risk_model"].quantile([0.9, 0.7])
    d["risk_band"] = np.select([d["attrition_risk_model"] >= q90, d["attrition_risk_model"] >= q70], ["High", "Elevated"], "Normal")
    d.loc[d["attrition_risk_model"].isna(), "risk_band"] = "Not scored"
    d["expected_revenue_at_risk"] = (d["est_annual_revenue"] * d["attrition_risk_model"]).round(2)
    d["action_hold"] = d["dq_flags"].fillna("").str.contains(HOLD_PATTERN)
    d.to_csv(SCORED, index=False, float_format="%.6f")

    # ---------------- summaries ----------------
    tot_rev = d["est_annual_revenue"].sum()
    seg = d.groupby("segment", observed=True).agg(
        customers=("customer_id", "size"), revenue=("est_annual_revenue", "sum"), median_revenue=("est_annual_revenue", "median"),
        avg_rei=("rei", "mean"), median_days_since_txn=("days_since_txn", "median"), avg_txn_90d=("txn_count_90d", "mean"),
        avg_products=("num_products", "mean"), main_bank_pct=("main_bank_flag", lambda s: (s == "Y").mean() * 100),
        app_active_pct=("app_logins_30d", lambda s: (s > 0).mean() * 100), median_deposits=("total_deposits", "median"),
        attrition_pct=("attrited_next_6m", lambda s: s.mean() * 100), avg_model_risk_pct=("attrition_risk_model", lambda s: s.mean() * 100),
        revenue_at_risk=("expected_revenue_at_risk", "sum"), avg_signals=("warning_signals", "mean"),
        median_age=("age", "median"), median_tenure_yrs=("tenure_months", lambda s: s.median() / 12)).reindex(SEGMENTS)
    seg["customer_share_pct"] = seg["customers"] / len(d) * 100
    seg["revenue_share_pct"] = seg["revenue"] / tot_rev * 100
    prod_cols = ["has_savings", "has_term_deposit", "has_credit_card", "has_personal_loan", "has_mortgage", "has_investments", "has_insurance"]
    prod = (d.groupby("segment", observed=True)[prod_cols].mean() * 100).reindex(SEGMENTS).round(1)
    sens = sensitivity(d)
    ct, km = kmeans_check(d)
    sig = signal_table(d)
    region = pd.crosstab(d["region"], d["segment"], normalize="index").mul(100).round(1)

    # ---------------- hypothetical interventions (assumption-driven, labelled) ----------------
    ad = d[d.segment == "Affluent Drifters"]; eb = d[d.segment == "Engaged Builders"]; lt = d[d.segment == "Light Touch"]
    scenarios = [
        {"segment": "Affluent Drifters", "intervention": "Relationship-manager re-engagement call + needs review",
         "assumption": "Outreach cuts their attrition probability by 25% (relative)",
         "customers": len(ad), "metric": "Expected annual revenue protected (USD)",
         "value": round(float(ad["expected_revenue_at_risk"].sum() * 0.25), 0)},
        {"segment": "Engaged Builders", "intervention": "Targeted cross-sell of one savings or card product",
         "assumption": "10% take up one product worth USD 180 a year",
         "customers": len(eb), "metric": "Incremental annual revenue (USD)", "value": round(len(eb) * 0.10 * 180, 0)},
        {"segment": "Light Touch", "intervention": "Digital activation (app onboarding, e-statements, bill-pay set-up)",
         "assumption": "15% become regular app users; their model risk falls to that of current regular app users in the segment",
         "customers": len(lt), "metric": "Customers retained (expected)", "value": None},
    ]
    reg = lt[lt["app_logins_30d"] >= 10]["attrition_risk_model"].mean(); non = lt[lt["app_logins_30d"] < 10]
    scenarios[2]["value"] = round(float(len(non) * 0.15 * max(non["attrition_risk_model"].mean() - reg, 0)), 1)

    pilot = []
    for nm, g, p0 in [("Affluent Drifters RM outreach", ad, ad["attrited_next_6m"].mean()),
                      ("Light Touch digital activation", lt, lt["attrited_next_6m"].mean()),
                      ("Engaged Builders cross-sell", eb, 0.05)]:
        n = int((~g["dq_flags"].fillna("").str.contains(HOLD_PATTERN)).sum()); arm = n // 2
        pilot.append({"cell": nm, "eligible": n, "treatment": n - arm, "holdout": arm, "baseline_rate_pct": round(float(p0) * 100, 1),
                      "min_detectable_change_pts": round(mde(arm, p0) * 100, 1)})

    S = {
        "snapshot_date": str(SNAPSHOT), "currency": "USD",
        "rows_raw": int(len(raw)), "customers": int(len(d)), "dq_steps": int(len(dq) - 1),
        "dq_rows_flagged": int((d["dq_flags"].fillna("") != "").sum()), "injected_issues": int(len(manifest)),
        "total_revenue": round(float(tot_rev), 0), "total_deposits": round(float(d["total_deposits"].sum()), 0),
        "total_lending": round(float(d["total_lending"].sum()), 0),
        "median_revenue": round(float(d["est_annual_revenue"].median()), 0), "avg_rei": round(float(d["rei"].mean()), 1),
        "attrition_pct": round(float(d["attrited_next_6m"].mean() * 100), 1),
        "active_30d_pct": round(float((d["days_since_txn"] <= 30).mean() * 100), 1),
        "app_active_pct": round(float((d["app_logins_30d"] > 0).mean() * 100), 1),
        "value_partial": int((d["value_basis"] != "All inputs available").sum()),
        "rei_partial": int((d["rei_basis"] != "All components").sum()),
        "action_hold": int(d["action_hold"].sum()),
        "segments": json.loads(seg.round(2).reset_index().to_json(orient="records")),
        "products": json.loads(prod.reset_index().to_json(orient="records")),
        "sensitivity": json.loads(sens.to_json(orient="records")),
        "kmeans": km, "signals": json.loads(sig.to_json(orient="records")),
        "model": mmetrics, "deciles": json.loads(deciles.to_json(orient="records")),
        "coefficients": json.loads(coef.to_json(orient="records")),
        "risk_bands": d["risk_band"].value_counts().to_dict(),
        "revenue_at_risk_total": round(float(d["expected_revenue_at_risk"].sum()), 0),
        "scenarios": scenarios, "pilot": pilot,
        "region_mix": json.loads(region.reset_index().to_json(orient="records")),
        "assumptions": {"revenue": REVENUE_ASSUMPTIONS, "card_revolving_share": CARD_REVOLVING_SHARE, "rei_weights": REI_WEIGHTS,
                        "value_bands": VALUE_BANDS, "engagement_bands": ENGAGEMENT_BANDS},
    }
    json.dump(S, open(REPORTS / "summary.json", "w"), indent=1)
    for nm, t in {"segment_summary": seg.round(2), "product_adoption_by_segment": prod, "sensitivity_tests": sens,
                  "warning_signals": sig, "model_deciles": deciles, "model_coefficients": coef,
                  "segment_vs_kmeans": ct, "region_mix_pct": region}.items():
        t.to_csv(REPORTS / f"{nm}.csv")
    pd.DataFrame(scenarios).to_csv(REPORTS / "hypothetical_scenarios.csv", index=False)
    pd.DataFrame(pilot).to_csv(REPORTS / "pilot_design.csv", index=False)
    print(seg[["customers", "customer_share_pct", "revenue_share_pct", "avg_rei", "attrition_pct"]].round(1).to_string())
    print(sens.to_string()); print(km); print(sig.to_string()); print(mmetrics); print(scenarios); print(pilot)


if __name__ == "__main__":
    main()
