"""Two-axis segmentation (Value x Engagement), plus sensitivity tests and a k-means comparison."""
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler
from .config import VALUE_BANDS, ENGAGEMENT_BANDS, SEGMENT_RULES, SEGMENTS, SEED
from .features import add_rei


def band(x, cut, labels=("High", "Mid", "Low")):
    return np.select([x >= cut["High"], x >= cut["Mid"]], labels[:2], labels[2])


def assign(d: pd.DataFrame, vb=VALUE_BANDS, eb=ENGAGEMENT_BANDS, rei_col="rei") -> pd.Series:
    v = band(d["est_annual_revenue"], vb)
    e = band(d[rei_col], eb)
    return pd.Series([SEGMENT_RULES[(a, b)] for a, b in zip(v, e)], index=d.index), v, e


def segment(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d["segment"], d["value_band"], d["engagement_band"] = assign(d)
    d["segment"] = pd.Categorical(d["segment"], SEGMENTS, ordered=True)
    return d


def sensitivity(d: pd.DataFrame) -> pd.DataFrame:
    base = d["segment"].astype(str)
    rows = []
    weight_sets = {
        "Recency-led (40/15/15/15/15)": {"recency": 40, "frequency": 15, "digital": 15, "adoption": 15, "loyalty": 15},
        "Adoption-led (25/15/15/30/15)": {"recency": 25, "frequency": 15, "digital": 15, "adoption": 30, "loyalty": 15},
        "Equal weights (20 each)": {"recency": 20, "frequency": 20, "digital": 20, "adoption": 20, "loyalty": 20},
        "No loyalty (35/25/15/25/0)": {"recency": 35, "frequency": 25, "digital": 15, "adoption": 25, "loyalty": 0},
        "Digital-led (25/15/30/15/15)": {"recency": 25, "frequency": 15, "digital": 30, "adoption": 15, "loyalty": 15},
    }
    for nm, w in weight_sets.items():
        alt = add_rei(d, w)
        s, _, _ = assign(alt)
        rows.append({"test": "REI weights", "scenario": nm, "same_segment_pct": (s == base).mean() * 100,
                     "adjusted_rand_index": adjusted_rand_score(base, s)})
    for nm, vb, eb in [("Value bands -20%", {"High": 1200, "Mid": 320}, ENGAGEMENT_BANDS),
                       ("Value bands +20%", {"High": 1800, "Mid": 480}, ENGAGEMENT_BANDS),
                       ("Engagement bands -5 pts", VALUE_BANDS, {"High": 65, "Mid": 45}),
                       ("Engagement bands +5 pts", VALUE_BANDS, {"High": 75, "Mid": 55})]:
        s, _, _ = assign(d, vb, eb)
        rows.append({"test": "Thresholds", "scenario": nm, "same_segment_pct": (s == base).mean() * 100,
                     "adjusted_rand_index": adjusted_rand_score(base, s)})
    out = pd.DataFrame(rows)
    out["same_segment_pct"] = out["same_segment_pct"].round(1); out["adjusted_rand_index"] = out["adjusted_rand_index"].round(3)
    return out


def kmeans_check(d: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    feats = pd.DataFrame({
        "log_revenue": np.log1p(d["est_annual_revenue"].clip(lower=0)),
        "recency": np.log1p(d["days_since_txn"].fillna(d["days_since_txn"].median())),   # diagnostic only
        "log_txn": np.log1p(d["txn_count_90d"]), "logins": np.log1p(d["app_logins_30d"]),
        "products": d["num_products"], "tenure": np.log1p(d["tenure_months"].fillna(d["tenure_months"].median())),
        "main_bank": (d["main_bank_flag"] == "Y").astype(int),
    })
    X = StandardScaler().fit_transform(feats)
    sil = {}
    for k in range(3, 9):
        lab = KMeans(k, n_init=10, random_state=SEED).fit_predict(X)
        sil[k] = round(float(silhouette_score(X, lab, sample_size=3000, random_state=SEED)), 3)
    lab6 = KMeans(6, n_init=10, random_state=SEED).fit_predict(X)
    ari = adjusted_rand_score(d["segment"].astype(str), lab6)
    ct = pd.crosstab(d["segment"], pd.Series(lab6, index=d.index, name="kmeans_cluster"))
    return ct, {"silhouette_by_k": sil, "ari_rule_vs_kmeans6": round(float(ari), 3)}
