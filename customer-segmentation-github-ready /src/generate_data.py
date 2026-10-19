"""Generate a fully SYNTHETIC retail-banking customer dataset.

Nothing here is derived from real customer records. Values come from a seeded latent-factor
simulation so that variables relate to each other plausibly (e.g. affluence drives income and
balances; age shapes digital use and product mix; engagement drives activity and attrition).

A small number of realistic data-quality problems are then injected so the cleaning stage has
something genuine to do. Every injection is recorded in data/raw/injected_issues_manifest.csv so
the cleaning step can be validated against ground truth.

Run:  python -m src.generate_data
"""
import numpy as np
import pandas as pd
from .config import RAW, SEED, N_CUSTOMERS, SNAPSHOT

rng = np.random.default_rng(SEED)
N = N_CUSTOMERS
sig = lambda x: 1 / (1 + np.exp(-x))


def generate() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    # ---------------- latent traits (never published) ----------------
    affluence = rng.normal(0, 1, N)
    engage = rng.normal(0, 1, N)
    satisfaction = rng.normal(0, 1, N)

    # ---------------- demographics ----------------
    age = np.clip(np.round(rng.normal(45, 15, N)), 19, 88).astype(int)
    region = rng.choice(["Metro", "Urban", "Regional", "Rural"], N, p=[0.36, 0.30, 0.21, 0.13])
    emp = np.empty(N, dtype=object)
    for i, a in enumerate(age):
        if a < 25:
            p = {"Student": .38, "Salaried": .47, "Self-employed": .08, "Business owner": .02, "Not employed": .05, "Retired": 0}
        elif a < 63:
            p = {"Student": .01, "Salaried": .58, "Self-employed": .17, "Business owner": .12, "Not employed": .07, "Retired": .05}
        else:
            p = {"Student": 0, "Salaried": .16, "Self-employed": .08, "Business owner": .06, "Not employed": .03, "Retired": .67}
        emp[i] = rng.choice(list(p), p=np.array(list(p.values())) / sum(p.values()))
    gender = rng.choice(["Female", "Male", "Non-binary / undisclosed"], N, p=[0.49, 0.49, 0.02])

    base_inc = pd.Series(emp).map({"Salaried": 54000, "Self-employed": 50000, "Business owner": 78000, "Retired": 31000,
                                   "Student": 11000, "Not employed": 9000}).values
    reg_mult = pd.Series(region).map({"Metro": 1.25, "Urban": 1.05, "Regional": 0.90, "Rural": 0.80}).values
    age_curve = 1 + 0.35 * np.exp(-((age - 50) / 16) ** 2)
    income = np.round(base_inc * reg_mult * age_curve * np.exp(0.45 * affluence + rng.normal(0, 0.15, N)), -2)

    tenure_m = np.maximum(1, np.round((age - 18) * 12 * rng.beta(1.5, 3.2, N))).astype(int)
    digital = sig(1.3 - 0.06 * (age - 40) + 0.35 * (region == "Metro") - 0.3 * (region == "Rural") + rng.normal(0, 0.7, N))
    channel = np.where(rng.random(N) < digital * 0.8, "Digital", rng.choice(["Branch", "Partner"], N, p=[0.75, 0.25]))
    salaried_like = np.isin(emp, ["Salaried", "Retired"])
    main_bank = rng.random(N) < sig(-0.6 + 0.9 * engage + 0.7 * salaried_like + 0.2 * affluence)

    # ---------------- products ----------------
    has_sav = rng.random(N) < sig(0.6 + 0.6 * affluence + 0.3 * engage)
    has_td = rng.random(N) < sig(-1.7 + 0.035 * (age - 40) + 0.7 * affluence)
    has_card = (rng.random(N) < sig(-0.1 + 0.55 * affluence + 0.35 * engage)) & (emp != "Not employed")
    has_pl = rng.random(N) < sig(-1.9 + 0.35 * (age < 50) + 0.25 * engage - 0.2 * affluence)
    has_mort = rng.random(N) < sig(-2.1 + 0.7 * affluence + 1.0 * ((age >= 28) & (age <= 62)) - 1.5 * (emp == "Student"))
    has_inv = rng.random(N) < sig(-2.3 + 1.0 * affluence + 0.025 * (age - 40))
    has_ins = rng.random(N) < sig(-1.7 + 0.35 * engage + 0.6 * has_mort)

    # ---------------- balances (USD) ----------------
    ca_bal = np.round(income / 12 * np.exp(rng.normal(-0.2 + 0.25 * engage, 0.6, N)), 2)
    sav_bal = np.where(has_sav, np.round(np.minimum(income * np.exp(rng.normal(-1.3 + 0.45 * affluence, 0.75, N)), income * 8), 2), 0.0)
    td_bal = np.where(has_td, np.round(np.minimum(income * np.exp(rng.normal(-0.6 + 0.5 * affluence, 0.6, N)), income * 8), -2), 0.0)
    inv_bal = np.where(has_inv, np.round(np.minimum(income * np.exp(rng.normal(-0.3 + 0.6 * affluence, 0.8, N)), income * 12), 2), 0.0)
    mort_bal = np.where(has_mort, np.round(income * rng.uniform(1.2, 4.0, N), -2), 0.0)
    pl_bal = np.where(has_pl, np.round(rng.uniform(1500, 28000, N), -1), 0.0)
    card_limit = np.where(has_card, np.round(np.clip(income * rng.uniform(0.08, 0.25, N), 1000, 40000), -2), np.nan)
    stress = rng.normal(0, 1, N) - 0.4 * affluence
    card_util = np.where(has_card, np.round(np.clip(rng.beta(2, 4.5, N) * 100 + 18 * (stress > 1.2), 0, 100), 1), np.nan)

    # ---------------- activity & digital ----------------
    dormant = rng.random(N) < sig(-2.6 - 1.2 * engage)
    days_txn = np.where(dormant, rng.integers(95, 420, N), np.round(rng.exponential(3 + 10 * np.exp(-0.8 * engage), N))).astype(int)
    lam = np.exp(3.0 + 0.55 * engage + 0.35 * main_bank + 0.15 * affluence)
    txn_90 = np.where(dormant, rng.poisson(0.3, N), rng.poisson(lam)).astype(int)
    txn_90 = np.where((days_txn > 90), 0, np.maximum(txn_90, (days_txn <= 90).astype(int)))
    avg_ticket = np.clip(income / 1500 * np.exp(rng.normal(0, 0.35, N)), 8, 400)
    txn_val_90 = np.round(txn_90 * avg_ticket, 2)
    card_spend_90 = np.where(has_card, np.round(txn_val_90 * rng.uniform(0.15, 0.6, N), 2), 0.0)
    app_user = rng.random(N) < digital
    logins_30 = np.where(app_user & ~dormant, rng.poisson(np.exp(1.2 + 1.4 * digital + 0.35 * engage)), 0).astype(int)
    days_login = np.where(~app_user, np.nan, np.where(logins_30 > 0, rng.integers(0, 30, N),
                                                      rng.integers(31, 240, N))).astype(float)
    dig_share = np.where(txn_90 > 0, np.round(np.clip(digital * 0.95 + rng.normal(0, 0.1, N), 0, 1), 3), np.nan)

    # deposit trend over the last 6 months (signal of money leaving)
    deposits_now = ca_bal + sav_bal + td_bal
    drift = rng.normal(0.04, 0.10, N) - 0.10 * (stress > 1) - 0.12 * (satisfaction < -1.2) - 0.08 * dormant
    deposits_6m_ago = np.round(deposits_now / np.clip(1 + drift, 0.35, 2.0), 2)

    # ---------------- service ----------------
    complaints = rng.poisson(np.clip(0.18 + 0.35 * (satisfaction < -0.8) + 0.1 * (stress > 1), 0.02, None)).astype(int)
    nps_raw = np.clip(np.round(7.2 + 1.6 * satisfaction + 0.4 * engage - 0.7 * complaints + rng.normal(0, 1, N)), 0, 10)
    responded = rng.random(N) < 0.42
    nps = np.where(responded, nps_raw, np.nan)
    contact = rng.choice(["App push", "Email", "SMS", "Phone"], N, p=[0.32, 0.33, 0.2, 0.15])

    # ---------------- synthetic outcome: attrition in the following 6 months ----------------
    n_prod = 1 + has_sav + has_td + has_card + has_pl + has_mort + has_inv + has_ins
    logit = (-2.25 - 0.85 * engage - 0.22 * (n_prod - 1) - 0.55 * main_bank + 0.45 * np.minimum(complaints, 3)
             - 0.35 * satisfaction + 1.1 * (drift < -0.12) + 0.5 * dormant - 0.03 * np.minimum(tenure_m / 12, 15))
    attrited = rng.random(N) < sig(logit)

    upd = pd.Timestamp(SNAPSHOT) - pd.to_timedelta(rng.integers(0, 20, N), unit="D")
    df = pd.DataFrame({
        "customer_id": [f"CX{100001 + i}" for i in range(N)],
        "record_updated_at": upd.strftime("%Y-%m-%d"),
        "age": age, "gender": gender, "region": region, "employment_type": emp, "annual_income": income,
        "tenure_months": tenure_m, "onboarding_channel": channel, "main_bank_flag": np.where(main_bank, "Y", "N"),
        "has_savings": has_sav.astype(int), "has_term_deposit": has_td.astype(int), "has_credit_card": has_card.astype(int),
        "has_personal_loan": has_pl.astype(int), "has_mortgage": has_mort.astype(int), "has_investments": has_inv.astype(int),
        "has_insurance": has_ins.astype(int), "num_products": n_prod.astype(int),
        "current_account_avg_bal_3m": ca_bal, "savings_balance": sav_bal, "term_deposit_balance": td_bal,
        "investment_balance": inv_bal, "mortgage_balance": mort_bal, "personal_loan_balance": pl_bal,
        "credit_card_limit": card_limit, "card_utilisation_pct": card_util, "deposits_6m_ago": deposits_6m_ago,
        "txn_count_90d": txn_90, "txn_value_90d": txn_val_90, "card_spend_90d": card_spend_90,
        "last_txn_date": [(pd.Timestamp(SNAPSHOT) - pd.Timedelta(days=int(d))).strftime("%Y-%m-%d") for d in days_txn],
        "app_registered": np.where(app_user, "Y", "N"), "app_logins_30d": logins_30,
        "last_login_date": [("" if np.isnan(d) else (pd.Timestamp(SNAPSHOT) - pd.Timedelta(days=int(d))).strftime("%Y-%m-%d")) for d in days_login],
        "digital_txn_share": dig_share, "complaints_12m": complaints, "nps_score": nps, "contact_preference": contact,
        "attrited_next_6m": attrited.astype(int),
    })
    truth = df.copy()

    # ---------------- inject realistic data-quality issues ----------------
    man = []
    raw = df.copy()

    def pick(n, mask=None):
        pool = raw.index if mask is None else raw.index[mask]
        return rng.choice(pool, n, replace=False)

    i = pick(70); raw.loc[i, "region"] = rng.choice(["metro", "METRO", "Metropolitan", "urban ", "Rural Area", "regional"], len(i))
    man += [("region_variant_coding", int(x)) for x in i]
    i = pick(55); raw.loc[i, "employment_type"] = raw.loc[i, "employment_type"].str.upper() + " "
    man += [("employment_case_whitespace", int(x)) for x in i]
    i = pick(140, raw["last_login_date"] != "")
    raw.loc[i, "last_login_date"] = pd.to_datetime(raw.loc[i, "last_login_date"]).dt.strftime("%d/%m/%Y")
    man += [("login_date_ddmmyyyy", int(x)) for x in i]
    i = pick(38, (raw["annual_income"] > 20000) & (raw["employment_type"].str.strip().str.title() != "Student"))
    raw.loc[i, "annual_income"] = np.round(raw.loc[i, "annual_income"] / 1000, 1)
    man += [("income_recorded_in_thousands", int(x)) for x in i]
    i = pick(150); raw.loc[i, "annual_income"] = np.nan
    man += [("income_missing", int(x)) for x in i]
    i = pick(9); raw.loc[i, "age"] = rng.choice([0, 999, 150], len(i))
    man += [("age_sentinel_or_impossible", int(x)) for x in i]
    i = pick(24); raw.loc[i, "tenure_months"] = -1
    man += [("tenure_sentinel_minus_one", int(x)) for x in i]
    i = pick(14, raw["has_credit_card"] == 1); raw.loc[i, "card_utilisation_pct"] = np.round(rng.uniform(160, 900, len(i)), 1)
    man += [("card_utilisation_impossible", int(x)) for x in i]
    i = pick(11, raw["has_credit_card"] == 1); raw.loc[i, "credit_card_limit"] = np.nan
    man += [("card_limit_missing", int(x)) for x in i]
    i = pick(60); raw.loc[i, "num_products"] = raw.loc[i, "num_products"] + rng.choice([-1, 1, 2], len(i))
    man += [("num_products_stale", int(x)) for x in i]
    i = pick(18); raw.loc[i, "savings_balance"] = np.where(raw.loc[i, "has_savings"] == 1, -raw.loc[i, "savings_balance"], -250.0)
    man += [("savings_balance_negative", int(x)) for x in i]
    i = pick(7, raw["txn_count_90d"] > 0)
    raw.loc[i, "last_txn_date"] = (pd.Timestamp(SNAPSHOT) + pd.to_timedelta(rng.integers(3, 40, len(i)), unit="D")).strftime("%Y-%m-%d")
    man += [("last_txn_after_snapshot", int(x)) for x in i]

    # stale re-ingested snapshot: same customer, older record_updated_at, slightly different balances
    i = pick(45); stale = raw.loc[i].copy()
    stale["record_updated_at"] = (pd.to_datetime(stale["record_updated_at"]) - pd.to_timedelta(rng.integers(35, 90, len(i)), unit="D")).dt.strftime("%Y-%m-%d")
    stale["current_account_avg_bal_3m"] = np.round(stale["current_account_avg_bal_3m"] * rng.uniform(0.8, 1.2, len(i)), 2)
    stale["txn_count_90d"] = (stale["txn_count_90d"] * rng.uniform(0.7, 1.3, len(i))).round().astype(int)
    stale["source_row_type"] = "stale_snapshot"
    man += [("stale_snapshot_reingested", int(x)) for x in i]
    # exact duplicates
    i = pick(40); dups = raw.loc[i].copy(); dups["source_row_type"] = "exact_duplicate"
    man += [("exact_duplicate_row", int(x)) for x in i]
    raw["source_row_type"] = "original"
    raw = pd.concat([raw, stale, dups]).sample(frac=1, random_state=SEED).reset_index(drop=True)
    manifest = pd.DataFrame(man, columns=["issue", "truth_index"])
    manifest["customer_id"] = truth.loc[manifest["truth_index"], "customer_id"].values
    return raw, truth, manifest


if __name__ == "__main__":
    raw, truth, manifest = generate()
    RAW.parent.mkdir(parents=True, exist_ok=True)
    # source_row_type is generator ground truth: kept OUT of the published raw file, stored in the manifest only
    raw.drop(columns=["source_row_type"]).to_csv(RAW, index=False)
    manifest.drop(columns=["truth_index"]).to_csv(RAW.parent / "injected_issues_manifest.csv", index=False)
    print(f"raw rows: {len(raw):,}  customers: {raw.customer_id.nunique():,}  injected issues: {len(manifest):,}")
    print(manifest.issue.value_counts().to_string())
    print("attrition rate (truth):", round(truth.attrited_next_6m.mean() * 100, 1), "%")
