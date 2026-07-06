"""
Step 7 - Automatic investigation case generation.

Groups alerts per customer into a single investigation case (the way
a real analyst queue would dedupe multiple alerts on the same subject
into one case for investigation) and assigns a synthetic analyst and
priority so the dashboard/case queue looks realistic.
"""

import random
from datetime import datetime, timedelta

import pandas as pd

from src.logger import log_event

ANALYSTS = ["A. Fernandes", "R. Yadav", "S. Chen", "M. Ibrahim", "K. Novak", "P. Singh"]
STATUSES = ["Open", "Under Review", "Escalated", "Closed - No Action", "Closed - SAR Filed"]


def _priority_from_score(score: float) -> str:
    if score >= 70:
        return "Critical"
    if score >= 45:
        return "High"
    if score >= 20:
        return "Medium"
    return "Low"


def generate_cases(alerts: pd.DataFrame, transactions: pd.DataFrame,
                    risk_scores: pd.DataFrame) -> pd.DataFrame:
    if alerts.empty:
        log_event("CASE_MANAGEMENT", "No alerts present - no cases generated")
        return pd.DataFrame(columns=[
            "case_number", "customer_id", "reason", "evidence", "risk_score",
            "triggered_rules", "transaction_count", "status", "assigned_analyst",
            "priority", "date_created",
        ])

    risk_lookup = risk_scores.set_index("customer_id")["risk_score"].to_dict()
    cases = []
    random.seed(42)

    for i, (cust_id, grp) in enumerate(alerts.groupby("customer_id")):
        rules_triggered = grp["rule_name"].unique().tolist()
        txn_ids = grp["transaction_id"].dropna().unique().tolist()
        cust_txns = transactions[transactions["customer_id"] == cust_id]
        score = risk_lookup.get(cust_id, grp["risk_score"].max())

        evidence = "; ".join(grp["reason"].head(3).tolist())
        created = datetime.now() - timedelta(days=random.randint(0, 45))

        cases.append({
            "case_number": f"CASE-{i+1:05d}",
            "customer_id": cust_id,
            "reason": f"{len(rules_triggered)} rule(s) triggered: {', '.join(rules_triggered)}",
            "evidence": evidence,
            "risk_score": score,
            "triggered_rules": ", ".join(rules_triggered),
            "transaction_count": len(cust_txns),
            "status": random.choices(
                STATUSES, weights=[35, 25, 15, 15, 10])[0],
            "assigned_analyst": random.choice(ANALYSTS),
            "priority": _priority_from_score(score),
            "date_created": created.date().isoformat(),
        })

    df = pd.DataFrame(cases).sort_values("risk_score", ascending=False).reset_index(drop=True)
    log_event("CASE_MANAGEMENT", f"Generated {len(df)} investigation cases")
    return df
