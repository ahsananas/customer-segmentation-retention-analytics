"""Retention: rule-based warning signals and a transparent logistic-regression attrition model.

The outcome `attrited_next_6m` is part of the SYNTHETIC dataset. It was generated from the same latent
traits as the features, so model performance here demonstrates method, not real-world predictive power.
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from .config import SEED

SIGNALS = {
    "No transaction for 45+ days": lambda d: d["days_since_txn"] >= 45,
    "Deposits down 15%+ over 6 months": lambda d: d["deposit_change_6m_pct"] <= -15,
    "2+ complaints in 12 months": lambda d: d["complaints_12m"] >= 2,
    "App registered but unused 30+ days": lambda d: (d["app_registered"] == "Y") & (d["days_since_login"] > 30),
    "Current account only": lambda d: d["num_products"] == 1,
    "Not main bank": lambda d: d["main_bank_flag"] == "N",
    "Card utilisation 85%+": lambda d: d["card_utilisation_pct"] >= 85,
}
MODEL_FEATURES = ["rei_recency", "rei_frequency", "rei_digital", "rei_adoption", "rei_loyalty",
                  "log_revenue", "deposit_change_6m_pct", "complaints_12m", "main_bank"]


def signal_table(d: pd.DataFrame) -> pd.DataFrame:
    base = d["attrited_next_6m"].mean()
    rows = []
    for nm, f in SIGNALS.items():
        m = f(d).fillna(False).astype(bool)
        rows.append({"signal": nm, "customers_flagged": int(m.sum()), "share_of_book_pct": round(m.mean() * 100, 1),
                     "attrition_if_present_pct": round(d.loc[m, "attrited_next_6m"].mean() * 100, 1),
                     "attrition_if_absent_pct": round(d.loc[~m, "attrited_next_6m"].mean() * 100, 1),
                     "lift_vs_book": round(d.loc[m, "attrited_next_6m"].mean() / base, 2)})
    return pd.DataFrame(rows).sort_values("lift_vs_book", ascending=False).reset_index(drop=True)


def add_signal_count(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    for nm, f in SIGNALS.items():
        d["sig_" + nm] = f(d).fillna(False).astype(int)
    d["warning_signals"] = d[[c for c in d.columns if c.startswith("sig_")]].sum(axis=1)
    return d


def model(d: pd.DataFrame):
    X = d.assign(log_revenue=np.log1p(d["est_annual_revenue"].clip(lower=0)),
                 main_bank=(d["main_bank_flag"] == "Y").astype(int))[MODEL_FEATURES]
    ok = X.notna().all(axis=1)          # records with a missing model input are not scored (no imputation)
    Xo, yo = X[ok], d.loc[ok, "attrited_next_6m"]
    Xtr, Xte, ytr, yte = train_test_split(Xo, yo, test_size=0.3, random_state=SEED, stratify=yo)
    sc = StandardScaler().fit(Xtr)
    lr = LogisticRegression(max_iter=1000).fit(sc.transform(Xtr), ytr)
    pte = lr.predict_proba(sc.transform(Xte))[:, 1]
    auc = roc_auc_score(yte, pte); brier = brier_score_loss(yte, pte)
    te = pd.DataFrame({"p": pte, "y": yte.values}).sort_values("p", ascending=False)
    te["decile"] = np.ceil(np.arange(1, len(te) + 1) / len(te) * 10).astype(int)
    dec = te.groupby("decile").agg(customers=("y", "size"), predicted_pct=("p", "mean"), actual_pct=("y", "mean")).reset_index()
    dec[["predicted_pct", "actual_pct"]] = (dec[["predicted_pct", "actual_pct"]] * 100).round(1)
    dec["lift"] = (dec["actual_pct"] / (yte.mean() * 100)).round(2)
    coef = pd.DataFrame({"feature": MODEL_FEATURES, "std_coefficient": lr.coef_[0].round(3)}).sort_values("std_coefficient")
    p_all = pd.Series(np.nan, index=d.index)
    p_all[ok] = lr.predict_proba(sc.transform(Xo))[:, 1]
    metrics = {"auc_test": round(float(auc), 3), "brier_test": round(float(brier), 4), "n_train": int(len(Xtr)),
               "n_test": int(len(Xte)), "not_scored_missing_input": int((~ok).sum()),
               "base_rate_pct": round(float(yo.mean() * 100), 1),
               "top_decile_lift": float(dec.loc[dec.decile == 1, "lift"].iloc[0])}
    return p_all, metrics, dec, coef
