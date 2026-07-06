"""
AML Transaction Monitoring System - main pipeline.

Run with:
    python main.py

This executes the full pipeline end to end:
    1. Generate synthetic data
    2. Clean & validate
    3. Run the AML rule engine
    4. Run ML anomaly detection
    5. Calculate customer risk scores
    6. Generate investigation cases
    7. Persist everything to SQLite
    8. Generate Excel reports
    9. Generate charts

Then launch the dashboard separately with:
    streamlit run dashboard/app.py
"""

import sys
import time

from src.data_generator import generate_all
from src.data_cleaner import run_cleaning
from src.rule_engine import run_all_rules
from src.anomaly_detection import run_anomaly_detection
from src.risk_scoring import calculate_risk_scores
from src.case_manager import generate_cases
from src.database import persist_all
from src.report_generator import generate_all_reports
from src.chart_generator import generate_all_charts
from src.logger import log_event


def run_pipeline():
    start = time.time()
    log_event("PIPELINE", "=== AML Transaction Monitoring pipeline started ===")

    print("Step 1-2: Generating synthetic customers, merchants, transactions...")
    customers, merchants, transactions = generate_all()

    print("Step 3: Cleaning and validating data...")
    customers, transactions = run_cleaning(customers, transactions)

    print("Step 6: Running Isolation Forest anomaly detection...")
    anomalies = run_anomaly_detection(transactions)
    transactions = transactions.merge(
        anomalies[["transaction_id", "anomaly_score", "is_anomaly"]],
        on="transaction_id", how="left",
    )

    print("Step 4: Running AML rule engine (15 rules)...")
    alerts = run_all_rules(customers, transactions, merchants)

    print("Step 5: Calculating weighted customer risk scores...")
    risk_scores = calculate_risk_scores(customers, transactions, alerts)

    print("Step 7: Generating investigation cases...")
    cases = generate_cases(alerts, transactions, risk_scores)

    print("Step 11: Persisting to SQLite...")
    persist_all(customers, transactions, merchants, alerts, cases, risk_scores)

    print("Step 9: Generating Excel reports...")
    generate_all_reports(customers, transactions, merchants, alerts, cases, risk_scores)

    print("Step 10: Generating charts...")
    generate_all_charts(customers, transactions, alerts, risk_scores)

    elapsed = time.time() - start
    log_event("PIPELINE", f"=== Pipeline completed in {elapsed:.1f}s ===")

    print(f"\nDone in {elapsed:.1f}s")
    print(f"  Customers:    {len(customers):,}")
    print(f"  Transactions: {len(transactions):,}")
    print(f"  Alerts:       {len(alerts):,}")
    print(f"  Cases:        {len(cases):,}")
    print("\nReports  -> reports/")
    print("Charts   -> charts/")
    print("Database -> database/aml_system.db")
    print("\nNow run:  streamlit run dashboard/app.py")


if __name__ == "__main__":
    try:
        run_pipeline()
    except Exception as exc:  # top-level guard so failures are logged, not silent
        log_event("PIPELINE_ERROR", str(exc))
        print(f"Pipeline failed: {exc}", file=sys.stderr)
        raise
