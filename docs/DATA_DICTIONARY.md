# Data dictionary (synthetic fields)

| Field | Type | Description |
|---|---|---|
| `customer_id` | text | Fictional pseudonymous customer identifier (CX100001–CX104000). No names or contact details are generated. |
| `record_updated_at` | date | Date the source record was last refreshed (used to resolve re-ingested snapshots) |
| `age` | integer | Customer age in years (synthetic) |
| `gender` | category | Female / Male / Non-binary or undisclosed (synthetic; descriptive only, never used in scoring) |
| `region` | category | Metro / Urban / Regional / Rural |
| `employment_type` | category | Salaried, Self-employed, Business owner, Retired, Student, Not employed |
| `annual_income` | number (USD) | Stated annual income (synthetic; descriptive only) |
| `tenure_months` | integer | Months since the relationship began |
| `onboarding_channel` | category | Digital / Branch / Partner |
| `main_bank_flag` | Y/N | Salary or main income credited to this bank |
| `has_savings … has_insurance` | 0/1 | Product holding flags (savings; term deposit; credit card; personal loan; mortgage; investments; insurance) |
| `num_products` | integer | Products held including the current account (= 1 + product flags, recalculated during cleaning) |
| `current_account_avg_bal_3m` | number (USD) | Average current-account balance over the last 3 months |
| `savings_balance / term_deposit_balance / investment_balance` | number (USD) | Balances at snapshot (0 when the product is not held) |
| `mortgage_balance / personal_loan_balance` | number (USD) | Outstanding lending balances |
| `credit_card_limit / card_utilisation_pct` | number | Card limit (USD) and utilisation (%) |
| `deposits_6m_ago` | number (USD) | Total deposits six months before the snapshot (for trend) |
| `txn_count_90d / txn_value_90d / card_spend_90d` | number | Transaction count and value (USD) in the 90 days to the snapshot |
| `last_txn_date / last_login_date` | date | Most recent transaction / app login (snapshot 2026-09-30) |
| `app_registered / app_logins_30d` | Y/N; integer | Mobile-app registration and logins in the last 30 days |
| `digital_txn_share` | 0–1 | Share of transactions made through digital channels |
| `complaints_12m` | integer | Complaints logged in the last 12 months |
| `nps_score` | 0–10 | Survey score (blank for non-respondents – about 58% of customers) |
| `contact_preference` | category | App push / Email / SMS / Phone |
| `attrited_next_6m` | 0/1 | SYNTHETIC outcome: customer closed the relationship in the 6 months after the snapshot |
| `days_since_txn / days_since_login` | integer | Derived during cleaning from the dates and the snapshot |
| `est_annual_revenue` | number (USD) | Revenue proxy = balances × illustrative margins + card interchange (see Assumptions) |
| `rei` | 0–100 | Relationship Engagement Index: recency 30, frequency 20, digital 15, product adoption 20, loyalty 15 |
| `segment` | category | Value band × engagement band → one of six segments |
| `attrition_risk_model` | 0–1 | Logistic-regression probability of attrition (synthetic outcome) |
| `expected_revenue_at_risk` | number (USD) | est_annual_revenue × attrition_risk_model |
| `dq_flags` | text | Cleaning flags applied to the record |
