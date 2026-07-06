# AML Transaction Monitoring System

A complete, end-to-end Anti-Money Laundering transaction monitoring system built in Python — synthetic data generation, a 15-rule detection engine, ML-based anomaly detection, weighted customer risk scoring, automated case management, Excel reporting, and an interactive Streamlit dashboard, all backed by SQLite.

Built as a portfolio project to demonstrate practical skills for **AML Analyst / Transaction Monitoring Analyst / FinCrime Analyst / Compliance Analyst** roles.

> All data is synthetically generated. No real customer, transaction, or institutional data is used anywhere in this project.

---

## Project Overview

The system simulates a bank's internal transaction monitoring stack:

1. Generates a realistic synthetic dataset (500 customers, 50 merchants, ~10,000+ transactions, including deliberately seeded suspicious patterns).
2. Cleans and validates the data, logging every step.
3. Runs it through a 15-rule AML detection engine (structuring, velocity, sanctions, PEP, etc.).
4. Runs an Isolation Forest anomaly detection model over transaction features.
5. Combines both signals into a transparent, weighted customer risk score (Low/Medium/High/Critical).
6. Auto-generates investigation cases from alerts, with assigned analysts, priority, and status.
7. Persists everything to SQLite.
8. Produces 7 Excel reports and 10 charts.
9. Serves it all through a multi-tab Streamlit dashboard.

## Architecture

```
project/
├── data/
│   ├── raw/            # generated CSVs (customers, transactions, merchants)
│   ├── processed/      # (reserved for cleaned intermediate exports)
│   └── generated/      # audit_log.txt and other run artifacts
├── database/
│   └── aml_system.db   # SQLite database: customers, transactions, merchants,
│                        # alerts, cases, risk_scores, countries, audit_logs
├── models/
│   └── isolation_forest.joblib
├── reports/             # 7 auto-generated Excel reports
├── charts/               # 10 auto-generated PNG charts
├── dashboard/
│   └── app.py           # Streamlit dashboard (6 tabs)
├── src/
│   ├── config/settings.py     # all thresholds/weights in one place
│   ├── data_generator.py      # Step 1-2
│   ├── data_cleaner.py        # Step 3
│   ├── rule_engine.py         # Step 4 - 15 rules
│   ├── risk_scoring.py        # Step 5
│   ├── anomaly_detection.py   # Step 6 - Isolation Forest
│   ├── case_manager.py        # Step 7
│   ├── database.py            # Step 11
│   ├── report_generator.py    # Step 9
│   ├── chart_generator.py     # Step 10
│   └── logger.py              # Step 12 - audit logging
├── tests/
│   └── test_rules.py    # Step 13 - unit tests
├── main.py               # runs the full pipeline
├── requirements.txt
└── README.md
```

**Data flow:** `data_generator` → `data_cleaner` → `anomaly_detection` (ML) → `rule_engine` (15 rules, now aware of ML flags) → `risk_scoring` (combines rules + ML into one score) → `case_manager` (dedupes alerts into cases) → `database` (persist) → `report_generator` / `chart_generator` (output) → `dashboard/app.py` (presentation layer, reads straight from SQLite).

## Installation

```bash
git clone <your-repo-url>
cd aml-transaction-monitoring
pip install -r requirements.txt

# Run the full pipeline: generates data, runs rules/ML, builds reports & charts
python main.py

# Launch the dashboard
streamlit run dashboard/app.py
```

Re-running `python main.py` regenerates a fresh synthetic dataset and rebuilds every table/report/chart from scratch (deterministic — seeded with `RANDOM_SEED = 42` in `src/config/settings.py`).

## Features

- **Synthetic but realistic data**: 500 customers (retail/business/corporate, PEPs, sanctioned entities, dormant/new accounts) and 10,000+ transactions across high/medium/low-risk countries, multiple currencies and channels, with suspicious patterns deliberately seeded so the rules have real positives to catch.
- **15-rule detection engine** (see below), each independently unit-testable.
- **ML anomaly detection** via Isolation Forest, combined with rule output rather than replacing it.
- **Transparent weighted risk scoring** — every point is traceable to a named factor (PEP, sanctions, structuring, velocity, etc.), which matters for model validation and audit defensibility.
- **Automatic case generation** — alerts are deduplicated per customer into a single investigation case with evidence, assigned analyst, priority, and status.
- **7 Excel reports**: full investigation workbook, customer risk report, daily/monthly alert summaries, high-risk customer list, SAR-candidate report, executive summary.
- **10 charts** (matplotlib, static) plus fully interactive Plotly charts inside the dashboard.
- **6-tab Streamlit dashboard**: Executive Summary, Alerts, Risk & Customers, Cases, Charts, Search.
- **Full audit trail**: every pipeline stage logs to `data/generated/audit_log.txt` and the `audit_logs` SQLite table.
- **Unit tests** covering rule logic, risk banding, and data cleaning.

## AML Rules Implemented

| # | Rule | What it catches |
|---|------|------------------|
| 1 | Large Cash Transaction | Cash deposits ≥ $10,000 (CTR-style threshold) |
| 2 | Round Amount Detection | Suspiciously "clean" amounts (e.g. exact 1,000s) |
| 3 | Just Below Reporting Threshold | Amounts sitting at 90-99% of the reporting threshold |
| 4 | High Risk Country Transfer | Transactions routed through FATF-style high-risk jurisdictions |
| 5 | Structuring (Smurfing) | 3+ sub-threshold deposits from one customer within 24h |
| 6 | Rapid Movement of Funds | 3+ outgoing transfers within 60 minutes |
| 7 | Velocity Detection | Daily transaction count spikes vs. customer baseline |
| 8 | Dormant Account Reactivation | Previously dormant account suddenly active |
| 9 | Sudden Increase in Transaction Volume | Monthly volume 5x above prior average |
| 10 | PEP Monitoring | Any activity from a Politically Exposed Person |
| 11 | Sanction Screening | Match against the internal sanctions flag |
| 12 | Unusual Merchant Activity | High-value activity with high-risk merchant categories (casinos, crypto, MSBs) |
| 13 | Multiple Accounts → Same Beneficiary | Many distinct senders paying one beneficiary in a short window |
| 14 | Multiple Countries in Short Time | Transactions across 3+ countries within 24h |
| 15 | Account Takeover Indicator | Same customer, same day, multiple devices/IPs |

All thresholds live in `src/config/settings.py` so they can be tuned and discussed like a real parameter register.

## Machine Learning

An **Isolation Forest** (`sklearn.ensemble.IsolationForest`, 3% contamination) is trained on behavioural features per transaction: USD-normalized amount, hour of day, day of week, high-risk-country flag, cash flag, and the customer's own transaction count/average amount. Its anomaly flag feeds into the weighted risk score as one more factor — the design intentionally treats ML as a *complementary* signal to the deterministic rules rather than a black-box replacement, which is how most real transaction monitoring systems are built and validated.

## Dashboard

`streamlit run dashboard/app.py` opens a 6-tab view: Executive Summary (KPIs, risk distribution, country heatmap), Alerts (filterable by rule/priority), Risk & Customers (top risky customers/merchants), Cases (investigation queue with status filter), Charts (interactive Plotly), and Search (customer/case lookup with drill-down transaction history).

## Future Improvements

- Swap the synthetic-only pipeline for a real (anonymized) dataset to validate rule thresholds against actual base rates.
- Add a proper case workflow (assignment, SLA timers, 4-eyes review, SAR e-filing template).
- Backtest the Isolation Forest against labeled historical SARs to measure precision/recall instead of an assumed contamination rate.
- Add network-graph analysis (e.g. NetworkX) for beneficiary/fund-flow clustering across the "same beneficiary" and "multi-country" rules.
- Containerize with Docker and add a lightweight FastAPI layer in front of SQLite for a more production-realistic deployment.

## Interview Talking Points

- **Why weighted scoring over a black-box model?** Regulators and internal model validation teams need to see exactly why a customer was scored the way they were — every point in this model traces to a named, documented factor.
- **Why combine rules and ML rather than pick one?** Rules catch known typologies with full explainability; ML catches novel patterns rules haven't been written for yet. Using ML output as one more scoring factor (not a filter that suppresses rule alerts) avoids the common trap of ML silently hiding true positives.
- **How structuring detection works**: a sliding time-window scan per customer for clusters of sub-threshold transactions — the same logic (conceptually) used in real transaction monitoring systems, just simplified.
- **Why alerts get deduplicated into cases**: a single customer often trips several rules at once; a real analyst queue works cases, not individual alerts, so this project mirrors that.
- **Data quality discipline**: every cleaning action (duplicates removed, invalid rows dropped, currency normalized to USD) is logged — this is exactly the kind of data lineage a QA/audit reviewer would ask about.

## Testing

```bash
pip install pytest
python -m pytest tests/ -v
```

## License

Portfolio/demo project. Not intended for production use or real financial decision-making.
