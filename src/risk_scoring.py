"""
Step 5 - Weighted customer risk scoring model.

Produces a 0-100+ point score per customer built from a transparent,
documented set of weighted factors, then buckets into Low / Medium /
High / Critical bands. This is deliberately simple and explainable -
real transaction monitoring risk models favour explainability over
complexity for regulatory and audit reasons.
"""

import pandas as pd

from src.config import settings
from src.logger import log_event


def _band(score: float) -> str:
    for low, high, label in settings.RISK_BANDS:
        if low <= score < high:
            return label
    return "Critical"


def calculate_risk_scores(customers: pd.DataFrame, transactions: pd.DataFrame,
                           alerts: pd.DataFrame) -> pd.DataFrame:
    w = settings.RISK_WEIGHTS
    alerts_per_customer = alerts.groupby("customer_id").size().to_dict()
    cash_txn_customers = set(
        transactions[(transactions["payment_type"] == "Cash Deposit") &
                     (transactions["amount_usd"] >= settings.LARGE_CASH_THRESHOLD)]["customer_id"]
    )
    structuring_customers = set(alerts[alerts["rule_name"] == "Structuring (Smurfing)"]["customer_id"])
    velocity_customers = set(alerts[alerts["rule_name"] == "Velocity Detection"]["customer_id"])
    dormant_customers = set(alerts[alerts["rule_name"] == "Dormant Account Reactivation"]["customer_id"])
    high_risk_country_customers = set(
        transactions[transactions["risk_country_flag"] == True]["customer_id"]  # noqa: E712
    )
    anomaly_customers = set(
        transactions[transactions.get("is_anomaly", False) == True]["customer_id"]  # noqa: E712
    ) if "is_anomaly" in transactions.columns else set()

    rows = []
    for _, cust in customers.iterrows():
        cust_id = cust["customer_id"]
        score = 0
        factors = []

        if cust["pep_status"]:
            score += w["pep"]; factors.append("PEP")
        if cust["sanction_status"]:
            score += w["sanction"]; factors.append("Sanction Match")
        if cust_id in high_risk_country_customers:
            score += w["high_risk_country"]; factors.append("High Risk Country")
        if cust_id in structuring_customers:
            score += w["structuring"]; factors.append("Structuring Pattern")
        if cust_id in velocity_customers:
            score += w["high_velocity"]; factors.append("High Velocity")
        if cust_id in cash_txn_customers:
            score += w["large_cash"]; factors.append("Large Cash Activity")
        if cust_id in dormant_customers:
            score += w["dormant_reactivation"]; factors.append("Dormant Reactivation")
        prior_alerts = alerts_per_customer.get(cust_id, 0)
        if prior_alerts >= 2:
            score += w["previous_alerts"]; factors.append(f"{prior_alerts} Prior Alerts")
        if cust_id in anomaly_customers:
            score += w["anomaly_ml"]; factors.append("ML Anomaly Flag")

        rows.append({
            "customer_id": cust_id,
            "risk_score": score,
            "risk_band": _band(score),
            "contributing_factors": ", ".join(factors) if factors else "None",
            "total_alerts": prior_alerts,
        })

    df = pd.DataFrame(rows)
    log_event("RISK_SCORING", f"Scored {len(df)} customers - "
              f"band counts: {df['risk_band'].value_counts().to_dict()}")
    return df
