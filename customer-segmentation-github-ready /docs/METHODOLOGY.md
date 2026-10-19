# Methodology

Every value below is a **model assumption** chosen for a synthetic portfolio. All of them sit in `src/config.py` and on the `Assumptions` sheet of the workbook.

## 1. Synthetic data generation
Hidden traits drive the observable fields, so variables are related rather than independent:
- **Affluence** drives income, balances, investments and mortgages.
- **Engagement** drives transaction recency and frequency, logins and main-bank status.
- **Digital propensity** declines with age and is higher in Metro areas.
- **Satisfaction** drives NPS and complaints.

The 6-month attrition outcome is drawn from a logistic function of engagement, product depth, main-bank status, complaints, deposit trend and tenure. A fixed random seed makes the data byte-reproducible; the snapshot date is 2026-09-30.

## 2. Value axis: estimated annual revenue (proxy)
| Component | Rate |
|---|---|
| current account margin | 2.50% |
| savings margin | 1.20% |
| term deposit margin | 0.80% |
| investment fee | 0.75% |
| mortgage margin | 1.10% |
| personal loan margin | 4.50% |
| card revolve margin | 12.00% |
| card interchange | 1.20% |
| card revolving share of utilised balance | 50% |

Card interchange is applied to 90-day card spend × 4. Value bands: **High ≥ $1,500**, **Mid ≥ $400**, Low below. The cut-offs are fixed round values close to the 70th and 30th percentiles of the synthetic book. Fixed values mean a customer changes band only when their own behaviour changes.

## 3. Engagement axis: Relationship Engagement Index (REI, 0–100)
| Component | Weight | Formula | Why |
|---|---|---|---|
| Recency | 30 | 30 × 0.5^(days since last transaction / 30) | The most immediate sign of an active relationship. A continuous decay avoids cliff edges. |
| Frequency | 20 | 20 × min(1, ln(1+txns 90d) / ln(121)) | Habitual use; the log scale stops heavy users dominating |
| Digital | 15 | 15 × (0.6·min(1, logins/20) + 0.4·digital share) | Lower cost to serve and a sticky channel |
| Product adoption | 20 | 20 × min(1, (products − 1)/4) | Product breadth raises switching costs |
| Loyalty | 15 | 15 × (0.40·tenure/10y + 0.35·main bank + 0.25·complaint-free) | Long-term attachment. NPS is excluded because 58% of customers didn't respond. |

If recency is unknown, the index is rescaled over the remaining components. If tenure is unknown, loyalty is scored on main-bank status and complaints. Engagement bands: **High ≥ 70**, **Mid ≥ 50**. Bands are applied to the unrounded index.

## 4. Segment rules
| Value band | Engagement band | Segment |
|---|---|---|
| High | High | Premier Advocates |
| High | Mid | Established Core |
| Mid | Mid | Established Core |
| High | Low | Affluent Drifters |
| Mid | High | Engaged Builders |
| Low | High | Engaged Builders |
| Mid | Low | Light Touch |
| Low | Mid | Light Touch |
| Low | Low | Dormant & Low Value |

## 5. Sensitivity and comparison
| Test | Scenario | Same segment | Adjusted Rand index |
|---|---|---|---|
| REI weights | Recency-led (40/15/15/15/15) | 89.7% | 0.757 |
| REI weights | Adoption-led (25/15/15/30/15) | 86.8% | 0.707 |
| REI weights | Equal weights (20 each) | 88.6% | 0.737 |
| REI weights | No loyalty (35/25/15/25/0) | 88.0% | 0.723 |
| REI weights | Digital-led (25/15/30/15/15) | 84.4% | 0.654 |
| Thresholds | Value bands -20% | 92.9% | 0.836 |
| Thresholds | Value bands +20% | 93.9% | 0.853 |
| Thresholds | Engagement bands -5 pts | 80.1% | 0.569 |
| Thresholds | Engagement bands +5 pts | 79.1% | 0.567 |

**k-means comparison:** clustering seven standardised behaviours gives silhouette scores of k=3: 0.205, k=4: 0.206, k=5: 0.203, k=6: 0.216, k=7: 0.212, k=8: 0.224. That indicates weak natural structure, and agreement with the rule-based segments is ARI 0.184. The rule-based approach is kept because it is transparent, stable and maps each segment to an action. A median-filled copy of the features is used for this diagnostic only.

## 6. Retention
**Warning signals:** each signal's attrition rate when present is compared with the book rate (lift). **Model:** a standardised logistic regression on 9 features, with a stratified 70/30 split (seed fixed). Test AUC is 0.806, Brier score 0.0751 and top-decile lift 3.84×. 7 customers with a missing input are not scored.

| Feature (standardised) | Coefficient |
|---|---|
| rei_frequency | -0.476 |
| rei_adoption | -0.319 |
| main_bank | -0.262 |
| deposit_change_6m_pct | -0.257 |
| rei_loyalty | -0.257 |
| rei_recency | -0.084 |
| rei_digital | -0.056 |
| log_revenue | +0.155 |
| complaints_12m | +0.297 |

## 7. Hypothetical interventions (illustrative, assumption-driven)
| Segment | Intervention | Assumption | Sizing |
|---|---|---|---|
| Affluent Drifters | Relationship-manager re-engagement call + needs review | Outreach cuts their attrition probability by 25% (relative) | Expected annual revenue protected (USD): $45k |
| Engaged Builders | Targeted cross-sell of one savings or card product | 10% take up one product worth USD 180 a year | Incremental annual revenue (USD): $10k |
| Light Touch | Digital activation (app onboarding, e-statements, bill-pay set-up) | 15% become regular app users; their model risk falls to that of current regular app users in the segment | Customers retained (expected): 4.8 |

## 8. Pilot design
Random 50/50 split into treatment and holdout, excluding records on hold. Minimum detectable change = 2.80 × √(2·p·(1−p)/n) (95% confidence, 80% power). This is indicative only.

| Cell | Treatment / holdout | Baseline | Detectable change |
|---|---|---|---|
| Affluent Drifters RM outreach | 91 / 91 | 28.4% | ±18.7 pts |
| Light Touch digital activation | 548 / 547 | 10.6% | ±5.2 pts |
| Engaged Builders cross-sell | 273 / 273 | 5.0% | ±5.2 pts |
