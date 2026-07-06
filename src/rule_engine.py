"""
Step 4 - AML Rule Engine.

Each rule is implemented as its own function so it can be unit tested,
tuned, and explained independently - this mirrors how a real rule
library / parameter register is documented for model validation.

Every rule returns a list of alert dicts:
    customer_id, transaction_id, rule_name, risk_score, reason, priority
"""

from datetime import timedelta

import pandas as pd

from src.config import settings
from src.logger import log_event

PRIORITY_MAP = {range(0, 30): "Low", range(30, 60): "Medium", range(60, 100): "High"}


def _priority(score: int) -> str:
    if score >= 60:
        return "High"
    if score >= 30:
        return "Medium"
    return "Low"


def rule_large_cash(txns: pd.DataFrame) -> list:
    hits = txns[(txns["payment_type"] == "Cash Deposit") &
                (txns["amount_usd"] >= settings.LARGE_CASH_THRESHOLD)]
    return [{
        "customer_id": r.customer_id, "transaction_id": r.transaction_id,
        "rule_name": "Large Cash Transaction", "risk_score": 40,
        "reason": f"Cash deposit of {r.amount_usd:,.0f} USD exceeds "
                  f"{settings.LARGE_CASH_THRESHOLD:,} threshold",
        "priority": _priority(40),
    } for r in hits.itertuples()]


def rule_round_amount(txns: pd.DataFrame) -> list:
    hits = txns[(txns["amount"] % settings.ROUND_AMOUNT_MODULO == 0) & (txns["amount"] >= 1000)]
    return [{
        "customer_id": r.customer_id, "transaction_id": r.transaction_id,
        "rule_name": "Round Amount Detection", "risk_score": 15,
        "reason": f"Suspiciously round amount of {r.amount:,.0f} {r.currency}",
        "priority": _priority(15),
    } for r in hits.itertuples()]


def rule_just_below_threshold(txns: pd.DataFrame) -> list:
    low = settings.STRUCTURING_THRESHOLD * settings.JUST_BELOW_THRESHOLD_PCT
    hits = txns[(txns["amount_usd"] >= low) & (txns["amount_usd"] < settings.STRUCTURING_THRESHOLD)]
    return [{
        "customer_id": r.customer_id, "transaction_id": r.transaction_id,
        "rule_name": "Just Below Reporting Threshold", "risk_score": 35,
        "reason": f"Amount {r.amount_usd:,.0f} USD sits just under the "
                  f"{settings.STRUCTURING_THRESHOLD:,} reporting threshold",
        "priority": _priority(35),
    } for r in hits.itertuples()]


def rule_high_risk_country(txns: pd.DataFrame) -> list:
    hits = txns[txns["risk_country_flag"] == True]  # noqa: E712
    return [{
        "customer_id": r.customer_id, "transaction_id": r.transaction_id,
        "rule_name": "High Risk Country Transfer", "risk_score": 30,
        "reason": f"Transaction routed through high-risk jurisdiction: {r.country}",
        "priority": _priority(30),
    } for r in hits.itertuples()]


def rule_structuring(txns: pd.DataFrame) -> list:
    alerts = []
    window = timedelta(hours=settings.STRUCTURING_WINDOW_HOURS)
    low = settings.STRUCTURING_THRESHOLD * settings.JUST_BELOW_THRESHOLD_PCT
    candidates = txns[(txns["amount_usd"] >= low) &
                       (txns["amount_usd"] < settings.STRUCTURING_THRESHOLD)]
    for cust_id, grp in candidates.groupby("customer_id"):
        grp = grp.sort_values("timestamp")
        times = grp["timestamp"].tolist()
        for i in range(len(times)):
            window_slice = grp[(grp["timestamp"] >= times[i]) & (grp["timestamp"] < times[i] + window)]
            if len(window_slice) >= settings.STRUCTURING_MIN_COUNT:
                alerts.append({
                    "customer_id": cust_id, "transaction_id": window_slice.iloc[0]["transaction_id"],
                    "rule_name": "Structuring (Smurfing)", "risk_score": 65,
                    "reason": f"{len(window_slice)} transactions just under the reporting "
                              f"threshold within {settings.STRUCTURING_WINDOW_HOURS}h "
                              f"(total {window_slice['amount_usd'].sum():,.0f} USD)",
                    "priority": _priority(65),
                })
                break  # one alert per customer is enough
    return alerts


def rule_rapid_movement(txns: pd.DataFrame) -> list:
    alerts = []
    window = timedelta(minutes=settings.RAPID_MOVEMENT_WINDOW_MINUTES)
    out = txns[txns["direction"] == "Outgoing"]
    for cust_id, grp in out.groupby("customer_id"):
        grp = grp.sort_values("timestamp")
        times = grp["timestamp"].tolist()
        for i in range(len(times)):
            window_slice = grp[(grp["timestamp"] >= times[i]) & (grp["timestamp"] < times[i] + window)]
            if len(window_slice) >= settings.RAPID_MOVEMENT_MIN_COUNT:
                alerts.append({
                    "customer_id": cust_id, "transaction_id": window_slice.iloc[0]["transaction_id"],
                    "rule_name": "Rapid Movement of Funds", "risk_score": 55,
                    "reason": f"{len(window_slice)} outgoing transfers within "
                              f"{settings.RAPID_MOVEMENT_WINDOW_MINUTES} minutes "
                              f"(total {window_slice['amount_usd'].sum():,.0f} USD)",
                    "priority": _priority(55),
                })
                break
    return alerts


def rule_velocity(txns: pd.DataFrame, customers: pd.DataFrame) -> list:
    alerts = []
    daily_counts = (txns.assign(day=txns["timestamp"].dt.date)
                         .groupby(["customer_id", "day"]).size()
                         .reset_index(name="count"))
    avg_daily = daily_counts.groupby("customer_id")["count"].mean()
    for cust_id, day_grp in daily_counts.groupby("customer_id"):
        baseline = avg_daily.get(cust_id, 1)
        spikes = day_grp[day_grp["count"] >= max(5, baseline * settings.VELOCITY_MULTIPLIER)]
        for _, row in spikes.iterrows():
            sample_txn = txns[(txns["customer_id"] == cust_id)].iloc[0]["transaction_id"]
            alerts.append({
                "customer_id": cust_id, "transaction_id": sample_txn,
                "rule_name": "Velocity Detection", "risk_score": 45,
                "reason": f"{row['count']} transactions on {row['day']}, "
                          f"{settings.VELOCITY_MULTIPLIER}x above customer baseline",
                "priority": _priority(45),
            })
    return alerts


def rule_dormant_reactivation(txns: pd.DataFrame, customers: pd.DataFrame) -> list:
    dormant_ids = set(customers[customers["is_dormant"] == True]["customer_id"])  # noqa: E712
    hits = txns[txns["customer_id"].isin(dormant_ids)]
    alerts = []
    for cust_id, grp in hits.groupby("customer_id"):
        first_txn = grp.sort_values("timestamp").iloc[0]
        alerts.append({
            "customer_id": cust_id, "transaction_id": first_txn["transaction_id"],
            "rule_name": "Dormant Account Reactivation", "risk_score": 40,
            "reason": "Previously dormant account resumed transaction activity",
            "priority": _priority(40),
        })
    return alerts


def rule_volume_spike(txns: pd.DataFrame) -> list:
    alerts = []
    monthly = (txns.assign(month=txns["timestamp"].dt.to_period("M"))
                    .groupby(["customer_id", "month"])["amount_usd"].sum().reset_index())
    for cust_id, grp in monthly.groupby("customer_id"):
        grp = grp.sort_values("month")
        if len(grp) < 2:
            continue
        vals = grp["amount_usd"].tolist()
        for i in range(1, len(vals)):
            prior_avg = sum(vals[:i]) / i
            if prior_avg > 0 and vals[i] >= prior_avg * settings.VOLUME_SPIKE_MULTIPLIER:
                sample_txn = txns[txns["customer_id"] == cust_id].iloc[0]["transaction_id"]
                alerts.append({
                    "customer_id": cust_id, "transaction_id": sample_txn,
                    "rule_name": "Sudden Increase in Transaction Volume", "risk_score": 35,
                    "reason": f"Monthly volume of {vals[i]:,.0f} USD is "
                              f"{settings.VOLUME_SPIKE_MULTIPLIER}x prior average",
                    "priority": _priority(35),
                })
    return alerts


def rule_pep_monitoring(txns: pd.DataFrame, customers: pd.DataFrame) -> list:
    pep_ids = set(customers[customers["pep_status"] == True]["customer_id"])  # noqa: E712
    hits = txns[txns["customer_id"].isin(pep_ids)]
    alerts = []
    for cust_id, grp in hits.groupby("customer_id"):
        top = grp.sort_values("amount_usd", ascending=False).iloc[0]
        alerts.append({
            "customer_id": cust_id, "transaction_id": top["transaction_id"],
            "rule_name": "PEP Monitoring", "risk_score": 50,
            "reason": f"Politically Exposed Person activity - largest txn "
                      f"{top['amount_usd']:,.0f} USD",
            "priority": _priority(50),
        })
    return alerts


def rule_sanction_screening(txns: pd.DataFrame, customers: pd.DataFrame) -> list:
    sanctioned_ids = set(customers[customers["sanction_status"] == True]["customer_id"])  # noqa: E712
    hits = txns[txns["customer_id"].isin(sanctioned_ids)]
    return [{
        "customer_id": r.customer_id, "transaction_id": r.transaction_id,
        "rule_name": "Sanction Screening Match", "risk_score": 95,
        "reason": "Customer matches internal sanctions list - immediate escalation required",
        "priority": "High",
    } for r in hits.itertuples()]


def rule_unusual_merchant(txns: pd.DataFrame, merchants: pd.DataFrame) -> list:
    high_risk_merchants = set(merchants[merchants["high_risk_category"] == True]["merchant_id"])  # noqa: E712
    hits = txns[txns["merchant_id"].isin(high_risk_merchants) & (txns["amount_usd"] >= 3000)]
    return [{
        "customer_id": r.customer_id, "transaction_id": r.transaction_id,
        "rule_name": "Unusual Merchant Activity", "risk_score": 30,
        "reason": f"High-risk merchant category transaction: {r.merchant_name} "
                  f"({r.amount_usd:,.0f} USD)",
        "priority": _priority(30),
    } for r in hits.itertuples()]


def rule_same_beneficiary(txns: pd.DataFrame) -> list:
    # Proxy: many distinct customers paying the same merchant_id in a short window
    alerts = []
    window = timedelta(hours=settings.SAME_BENEFICIARY_WINDOW_HOURS)
    out = txns[txns["direction"] == "Outgoing"].sort_values("timestamp")
    for merchant_id, grp in out.groupby("merchant_id"):
        grp = grp.sort_values("timestamp")
        times = grp["timestamp"].tolist()
        for i in range(len(times)):
            window_slice = grp[(grp["timestamp"] >= times[i]) & (grp["timestamp"] < times[i] + window)]
            distinct_senders = window_slice["customer_id"].nunique()
            if distinct_senders >= settings.SAME_BENEFICIARY_MIN_SENDERS:
                for cust_id in window_slice["customer_id"].unique():
                    txn_id = window_slice[window_slice["customer_id"] == cust_id].iloc[0]["transaction_id"]
                    alerts.append({
                        "customer_id": cust_id, "transaction_id": txn_id,
                        "rule_name": "Multiple Accounts to Same Beneficiary", "risk_score": 45,
                        "reason": f"{distinct_senders} distinct customers sent funds to the same "
                                  f"beneficiary/merchant within {settings.SAME_BENEFICIARY_WINDOW_HOURS}h",
                        "priority": _priority(45),
                    })
                break
    return alerts


def rule_multi_country(txns: pd.DataFrame) -> list:
    alerts = []
    window = timedelta(hours=settings.MULTI_COUNTRY_WINDOW_HOURS)
    for cust_id, grp in txns.groupby("customer_id"):
        grp = grp.sort_values("timestamp")
        times = grp["timestamp"].tolist()
        for i in range(len(times)):
            window_slice = grp[(grp["timestamp"] >= times[i]) & (grp["timestamp"] < times[i] + window)]
            distinct_countries = window_slice["country"].nunique()
            if distinct_countries >= settings.MULTI_COUNTRY_MIN_COUNT:
                alerts.append({
                    "customer_id": cust_id, "transaction_id": window_slice.iloc[0]["transaction_id"],
                    "rule_name": "Multiple Countries in Short Time", "risk_score": 40,
                    "reason": f"Transactions across {distinct_countries} countries within "
                              f"{settings.MULTI_COUNTRY_WINDOW_HOURS}h",
                    "priority": _priority(40),
                })
                break
    return alerts


def rule_account_takeover(txns: pd.DataFrame) -> list:
    # Proxy indicator: same customer, same day, 3+ distinct device IDs and 2+ distinct IPs
    alerts = []
    daily = txns.assign(day=txns["timestamp"].dt.date)
    for (cust_id, day), grp in daily.groupby(["customer_id", "day"]):
        if grp["device_id"].nunique() >= 3 and grp["ip_address"].nunique() >= 2:
            alerts.append({
                "customer_id": cust_id, "transaction_id": grp.iloc[0]["transaction_id"],
                "rule_name": "Account Takeover Indicator", "risk_score": 50,
                "reason": f"{grp['device_id'].nunique()} devices and "
                          f"{grp['ip_address'].nunique()} IPs used on {day}",
                "priority": _priority(50),
            })
    return alerts


def run_all_rules(customers: pd.DataFrame, transactions: pd.DataFrame,
                   merchants: pd.DataFrame) -> pd.DataFrame:
    """Execute every rule and return a single consolidated alerts DataFrame."""
    all_alerts = []
    rule_funcs = [
        ("Large Cash Transaction", lambda: rule_large_cash(transactions)),
        ("Round Amount Detection", lambda: rule_round_amount(transactions)),
        ("Just Below Threshold", lambda: rule_just_below_threshold(transactions)),
        ("High Risk Country", lambda: rule_high_risk_country(transactions)),
        ("Structuring", lambda: rule_structuring(transactions)),
        ("Rapid Movement", lambda: rule_rapid_movement(transactions)),
        ("Velocity", lambda: rule_velocity(transactions, customers)),
        ("Dormant Reactivation", lambda: rule_dormant_reactivation(transactions, customers)),
        ("Volume Spike", lambda: rule_volume_spike(transactions)),
        ("PEP Monitoring", lambda: rule_pep_monitoring(transactions, customers)),
        ("Sanction Screening", lambda: rule_sanction_screening(transactions, customers)),
        ("Unusual Merchant", lambda: rule_unusual_merchant(transactions, merchants)),
        ("Same Beneficiary", lambda: rule_same_beneficiary(transactions)),
        ("Multi Country", lambda: rule_multi_country(transactions)),
        ("Account Takeover", lambda: rule_account_takeover(transactions)),
    ]

    for name, func in rule_funcs:
        result = func()
        all_alerts.extend(result)
        log_event("RULE_EXECUTION", f"Rule '{name}' generated {len(result)} alert(s)")

    df = pd.DataFrame(all_alerts)
    if df.empty:
        df = pd.DataFrame(columns=["customer_id", "transaction_id", "rule_name",
                                    "risk_score", "reason", "priority"])
    df.insert(0, "alert_id", [f"A{i+1:06d}" for i in range(len(df))])
    log_event("RULE_EXECUTION", f"Total alerts generated: {len(df)}")
    return df
