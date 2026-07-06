"""
Step 13 - Unit tests.

Run with:  python -m pytest tests/ -v
"""

import os
import sys
from datetime import datetime, timedelta

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import rule_engine, risk_scoring, data_cleaner  # noqa: E402


def _txn(**kwargs):
    base = {
        "transaction_id": "T1", "customer_id": "C1", "amount": 100.0,
        "amount_usd": 100.0, "currency": "USD", "country": "United States",
        "merchant_id": "M1", "merchant_name": "Test Merchant",
        "payment_type": "Card Payment", "account_type": "Current",
        "direction": "Outgoing", "device_id": "DEV1", "ip_address": "1.1.1.1",
        "channel": "Online", "risk_country_flag": False, "description": "test",
        "timestamp": datetime(2026, 1, 1, 10, 0, 0),
    }
    base.update(kwargs)
    return base


def test_large_cash_rule_flags_over_threshold():
    txns = pd.DataFrame([
        _txn(transaction_id="T1", payment_type="Cash Deposit", amount_usd=15000),
        _txn(transaction_id="T2", payment_type="Cash Deposit", amount_usd=500),
    ])
    alerts = rule_engine.rule_large_cash(txns)
    assert len(alerts) == 1
    assert alerts[0]["transaction_id"] == "T1"


def test_round_amount_rule():
    txns = pd.DataFrame([
        _txn(transaction_id="T1", amount=5000),
        _txn(transaction_id="T2", amount=4321.55),
    ])
    alerts = rule_engine.rule_round_amount(txns)
    ids = {a["transaction_id"] for a in alerts}
    assert "T1" in ids and "T2" not in ids


def test_high_risk_country_rule():
    txns = pd.DataFrame([
        _txn(transaction_id="T1", risk_country_flag=True, country="Iran"),
        _txn(transaction_id="T2", risk_country_flag=False, country="Germany"),
    ])
    alerts = rule_engine.rule_high_risk_country(txns)
    assert len(alerts) == 1
    assert alerts[0]["transaction_id"] == "T1"


def test_structuring_rule_detects_burst():
    base_time = datetime(2026, 1, 1, 8, 0, 0)
    txns = pd.DataFrame([
        _txn(transaction_id=f"T{i}", customer_id="C1", amount_usd=9500,
             timestamp=base_time + timedelta(hours=i * 2))
        for i in range(4)
    ])
    alerts = rule_engine.rule_structuring(txns)
    assert len(alerts) == 1
    assert alerts[0]["customer_id"] == "C1"


def test_structuring_rule_no_false_positive_when_spread_out():
    base_time = datetime(2026, 1, 1, 8, 0, 0)
    txns = pd.DataFrame([
        _txn(transaction_id=f"T{i}", customer_id="C1", amount_usd=9500,
             timestamp=base_time + timedelta(days=i * 10))
        for i in range(4)
    ])
    alerts = rule_engine.rule_structuring(txns)
    assert len(alerts) == 0


def test_sanction_screening_rule():
    txns = pd.DataFrame([_txn(transaction_id="T1", customer_id="C1")])
    customers = pd.DataFrame([{"customer_id": "C1", "sanction_status": True}])
    alerts = rule_engine.rule_sanction_screening(txns, customers)
    assert len(alerts) == 1
    assert alerts[0]["risk_score"] == 95


def test_risk_banding():
    assert risk_scoring._band(10) == "Low"
    assert risk_scoring._band(25) == "Medium"
    assert risk_scoring._band(50) == "High"
    assert risk_scoring._band(90) == "Critical"


def test_transaction_cleaning_removes_invalid_amounts():
    df = pd.DataFrame([
        _txn(transaction_id="T1", amount=100, currency="USD"),
        _txn(transaction_id="T2", amount=-50, currency="USD"),
        _txn(transaction_id="T3", amount=100, currency="USD"),  # duplicate id below
    ])
    df.loc[2, "transaction_id"] = "T1"  # force a duplicate
    cleaned = data_cleaner.clean_transactions(df)
    assert len(cleaned) == 1
    assert (cleaned["amount"] > 0).all()


def test_run_all_rules_returns_expected_columns():
    txns = pd.DataFrame([_txn(transaction_id="T1", customer_id="C1")])
    customers = pd.DataFrame([{
        "customer_id": "C1", "pep_status": False, "sanction_status": False,
        "is_dormant": False,
    }])
    merchants = pd.DataFrame([{
        "merchant_id": "M1", "merchant_name": "Test Merchant",
        "category": "Retail", "country": "United States", "high_risk_category": False,
    }])
    alerts = rule_engine.run_all_rules(customers, txns, merchants)
    expected_cols = {"alert_id", "customer_id", "transaction_id", "rule_name",
                      "risk_score", "reason", "priority"}
    assert expected_cols.issubset(set(alerts.columns))
