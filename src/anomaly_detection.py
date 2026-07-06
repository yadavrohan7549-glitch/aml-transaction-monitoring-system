"""
Step 6 - Machine learning anomaly detection.

Uses an Isolation Forest (unsupervised) over numeric/behavioural
transaction features to flag statistically unusual transactions that
rule-based logic might miss. The anomaly score is combined with the
rule-based alerts rather than replacing them - this mirrors how most
real transaction monitoring systems use ML as a complementary signal.
"""

import os

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from src.config import settings
from src.logger import log_event


FEATURE_COLUMNS = ["amount_usd", "hour_of_day", "day_of_week", "is_high_risk_country",
                    "is_cash", "customer_txn_count", "customer_avg_amount"]


def _build_features(transactions: pd.DataFrame) -> pd.DataFrame:
    df = transactions.copy()
    df["hour_of_day"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["is_high_risk_country"] = df["risk_country_flag"].astype(int)
    df["is_cash"] = (df["payment_type"] == "Cash Deposit").astype(int)

    cust_stats = df.groupby("customer_id")["amount_usd"].agg(["count", "mean"]).rename(
        columns={"count": "customer_txn_count", "mean": "customer_avg_amount"})
    df = df.merge(cust_stats, on="customer_id", how="left")
    return df


def run_anomaly_detection(transactions: pd.DataFrame, contamination=0.03,
                           save_model=True) -> pd.DataFrame:
    df = _build_features(transactions)
    X = df[FEATURE_COLUMNS].fillna(0).values

    model = IsolationForest(
        n_estimators=200, contamination=contamination,
        random_state=settings.RANDOM_SEED,
    )
    model.fit(X)

    raw_scores = model.decision_function(X)          # higher = more normal
    predictions = model.predict(X)                     # -1 = anomaly, 1 = normal

    df["anomaly_score"] = (-raw_scores)                # flip so higher = more anomalous
    df["is_anomaly"] = predictions == -1

    if save_model:
        os.makedirs(settings.MODELS_DIR, exist_ok=True)
        joblib.dump(model, os.path.join(settings.MODELS_DIR, "isolation_forest.joblib"))

    log_event("MACHINE_LEARNING",
              f"Isolation Forest flagged {df['is_anomaly'].sum()} anomalies "
              f"out of {len(df)} transactions ({contamination:.0%} contamination)")

    return df[["transaction_id", "customer_id", "anomaly_score", "is_anomaly"]]
