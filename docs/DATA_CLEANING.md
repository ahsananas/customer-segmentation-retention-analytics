# Data cleaning log

Principles: fix only what the data can justify, otherwise set the value to missing and flag it; **never impute financial or activity values**; log every rule.
The raw file contains 681 deliberately injected problems listed in `data/raw/injected_issues_manifest.csv`. `src/validate.py` checks that every one is detected.

| # | Check | Rule | Rows | Action | Rationale |
|---|---|---|---|---|---|
| 1 | Exact duplicate rows | All columns identical | 40 | Removed (first kept) | Double-loaded rows would double-count customers and balances. |
| 2 | Re-ingested older snapshots | Same customer_id appears more than once with different values | 45 | Kept the most recent record_updated_at; older rows removed | A customer has one current state; the newest snapshot is the authoritative one. |
| 3 | Region coding variants | e.g. 'metro', 'METRO', 'Metropolitan', 'Rural Area' | 70 | Mapped to Metro / Urban / Regional / Rural | Same meaning, different spelling. |
| 4 | Employment text case / whitespace | Upper-case values with trailing spaces | 55 | Trimmed and re-cased | Prevents one category splitting into two. |
| 5 | Mixed date formats (last_login_date) | DD/MM/YYYY mixed with ISO YYYY-MM-DD | 140 | Parsed each format explicitly | Guessing the format could swap day and month. |
| 6 | Transaction dated after the snapshot | last_txn_date > 2026-09-30 | 7 | Set to missing (recency unknown); flagged | A future date is impossible; the true date is unknown. |
| 7 | Impossible age | age < 18 or > 105 (values 0, 150, 999) | 9 | Set to missing | Looks like sentinel / keying values; true age unknown. Age is not used in the segmentation. |
| 8 | Sentinel tenure | tenure_months = -1 | 24 | Set to missing; loyalty score uses observed components only | -1 is a system placeholder for 'unknown'. |
| 9 | Income recorded in thousands | annual_income < 1,000 for a non-student (e.g. 54.3) | 36 | Multiplied by 1,000 | Values are plausible incomes once read as thousands; no annual income below USD 1,000 is credible for an earning adult. Income is descriptive only (not in the score). |
| 10 | Income missing | annual_income blank | 150 | Left missing (not imputed) | Income is not used in the segmentation, so no estimate is needed. |
| 11 | Impossible card utilisation | card_utilisation_pct > 150% | 14 | Set to missing | Small over-limit use is possible; 160–900% is not. |
| 12 | Card holder without a limit | has_credit_card = 1 and credit_card_limit blank | 11 | Left missing; revolving-balance revenue scored as 0 for these rows and flagged | Limit unknown – no value is invented. |
| 13 | Stale product count | num_products differs from 1 + product flags | 60 | Recalculated from the product flags | Flags are the system of record; the count field is derived. |
| 14 | Negative savings balance | savings_balance < 0 | 18 | 5 rows with no savings product set to 0; 13 rows with a savings product set to missing | Savings accounts cannot be negative. With no product the balance must be 0; otherwise the true value is unknown. |
| 15 | Row count reconciliation | 4,085 raw rows → 4,000 customers | 85 | Removed rows = exact duplicates + stale snapshots | Every customer_id is now unique. |

**Effects on scoring**
- 38 customers have a partially observed revenue proxy (a held product's balance or card input is missing). The missing component contributes nothing, and the record is flagged.
- 7 customers have an unknown recency (the transaction was dated after the snapshot). Their REI is rescaled over the other components.
- 33 records with uncertain key facts (impossible age, unknown recency, invalid savings balance) are excluded from pilot and outreach lists.
