"""
Step 1 & 2 - Generate realistic banking data.

Deliberately avoids a hard dependency on the `faker` library so the
project runs even in restricted/offline environments. Names/addresses
are built from curated lists instead - still produces varied, realistic
looking synthetic data with none of it referring to real people.
"""

import os
import random
import uuid
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from src.config import settings
from src.logger import log_event

random.seed(settings.RANDOM_SEED)
np.random.seed(settings.RANDOM_SEED)

FIRST_NAMES = [
    "Aarav", "Priya", "James", "Emma", "Liam", "Olivia", "Noah", "Ava",
    "Mohammed", "Fatima", "Wei", "Ling", "Carlos", "Sofia", "Ivan", "Elena",
    "Ahmed", "Sara", "David", "Grace", "Ethan", "Mia", "Lucas", "Zara",
    "Omar", "Nina", "Raj", "Anjali", "Tom", "Lucy",
]
LAST_NAMES = [
    "Sharma", "Khan", "Smith", "Johnson", "Wang", "Li", "Garcia", "Rossi",
    "Petrov", "Ali", "Brown", "Davies", "Kumar", "Patel", "Chen", "Novak",
    "Silva", "Muller", "Nguyen", "Okafor", "Yadav", "Cohen", "Andersen",
]
OCCUPATIONS = [
    "Software Engineer", "Business Owner", "Doctor", "Retired", "Student",
    "Import/Export Trader", "Consultant", "Real Estate Agent", "Accountant",
    "Restaurant Owner", "Freelancer", "Government Employee", "Unemployed",
    "Construction Contractor", "Crypto Trader", "Lawyer",
]
CUSTOMER_TYPES = ["Retail", "Business", "Corporate"]
KYC_STATUSES = ["Verified", "Pending Review", "Expired", "Enhanced Due Diligence"]
PAYMENT_TYPES = ["Wire Transfer", "Card Payment", "Cash Deposit", "ACH", "Crypto", "Cheque"]
CHANNELS = ["Online", "Mobile App", "Branch", "ATM", "Phone Banking"]
ACCOUNT_TYPES = ["Current", "Savings", "Business", "Corporate"]
MERCHANT_CATEGORIES = [
    "Retail", "Electronics", "Travel", "Casino/Gaming", "Jewelry", "Crypto Exchange",
    "Money Service Business", "Restaurant", "Real Estate", "Consulting Services",
    "Import/Export", "Online Marketplace",
]


def _random_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def _random_date(start_year=1955, end_year=2003):
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    return start + timedelta(days=random.randint(0, (end - start).days))


def generate_merchants(n=settings.NUM_MERCHANTS) -> pd.DataFrame:
    rows = []
    for i in range(n):
        category = random.choice(MERCHANT_CATEGORIES)
        rows.append({
            "merchant_id": f"M{i+1:04d}",
            "merchant_name": f"{random.choice(LAST_NAMES)} {category}",
            "category": category,
            "country": random.choice(settings.ALL_COUNTRIES),
            "high_risk_category": category in ["Casino/Gaming", "Crypto Exchange", "Money Service Business", "Jewelry"],
        })
    df = pd.DataFrame(rows)
    log_event("DATA_GENERATION", f"Generated {len(df)} merchants")
    return df


def generate_customers(n=settings.NUM_CUSTOMERS) -> pd.DataFrame:
    rows = []
    for i in range(n):
        country = random.choices(
            settings.ALL_COUNTRIES,
            weights=[3 if c in settings.HIGH_RISK_COUNTRIES else
                     2 if c in settings.MEDIUM_RISK_COUNTRIES else 10
                     for c in settings.ALL_COUNTRIES],
        )[0]

        pep = random.random() < 0.02          # ~2% PEPs
        sanctioned = random.random() < 0.005   # ~0.5% sanctioned entities
        dormant = random.random() < 0.05
        new_account = random.random() < 0.08

        customer_type = random.choices(CUSTOMER_TYPES, weights=[70, 22, 8])[0]
        income = round(np.random.lognormal(mean=9.5, sigma=0.6), 2)  # skewed income distribution

        opened = _random_date(2005, 2026) if not new_account else \
            datetime.now() - timedelta(days=random.randint(1, 60))
        last_activity_days_ago = random.randint(180, 900) if dormant else random.randint(0, 30)

        risk_level = "Low"
        if sanctioned:
            risk_level = "Critical"
        elif pep or country in settings.HIGH_RISK_COUNTRIES:
            risk_level = "High"
        elif country in settings.MEDIUM_RISK_COUNTRIES:
            risk_level = "Medium"

        rows.append({
            "customer_id": f"C{i+1:05d}",
            "name": _random_name(),
            "dob": _random_date().date().isoformat(),
            "occupation": random.choice(OCCUPATIONS),
            "income": income,
            "country": country,
            "nationality": country,
            "kyc_status": random.choices(KYC_STATUSES, weights=[80, 10, 5, 5])[0],
            "pep_status": pep,
            "sanction_status": sanctioned,
            "risk_level": risk_level,
            "expected_monthly_income": round(income / 12, 2),
            "expected_monthly_transactions": random.randint(5, 40),
            "expected_transaction_size": round(income / 12 / random.randint(3, 10), 2),
            "account_opening_date": opened.date().isoformat(),
            "customer_type": customer_type,
            "is_dormant": dormant,
            "last_activity_days_ago": last_activity_days_ago,
        })
    df = pd.DataFrame(rows)
    log_event("DATA_GENERATION",
              f"Generated {len(df)} customers "
              f"({df['pep_status'].sum()} PEPs, {df['sanction_status'].sum()} sanctioned)")
    return df


def generate_transactions(customers: pd.DataFrame, merchants: pd.DataFrame,
                           n=settings.NUM_TRANSACTIONS) -> pd.DataFrame:
    rows = []
    now = datetime.now()
    customer_ids = customers["customer_id"].tolist()
    customer_lookup = customers.set_index("customer_id")

    # Give a subset of customers a "structuring ring" and "rapid movement" pattern
    # so the rule engine has real positives to find - mirrors how test data is
    # deliberately seeded in real TM system UAT.
    structuring_customers = random.sample(customer_ids, k=15)
    rapid_movement_customers = random.sample(customer_ids, k=15)
    high_velocity_customers = random.sample(customer_ids, k=15)

    for i in range(n):
        cust_id = random.choice(customer_ids)
        cust = customer_lookup.loc[cust_id]
        merchant = merchants.sample(1).iloc[0]

        days_back = random.randint(0, 180)
        timestamp = now - timedelta(days=days_back, hours=random.randint(0, 23),
                                     minutes=random.randint(0, 59))

        base_amount = max(10, np.random.lognormal(mean=6.0, sigma=1.3))
        amount = round(base_amount, 2)

        # Inject structuring behaviour: several txns just under the threshold
        if cust_id in structuring_customers and random.random() < 0.4:
            amount = round(random.uniform(9000, 9950), 2)

        # Inject round-number "layering" style amounts occasionally
        if random.random() < 0.03:
            amount = float(random.choice([1000, 2000, 5000, 10000, 20000]))

        direction = random.choices(["Incoming", "Outgoing"], weights=[45, 55])[0]
        country = cust["country"] if random.random() < 0.7 else random.choice(settings.ALL_COUNTRIES)

        rows.append({
            "transaction_id": f"T{i+1:07d}",
            "customer_id": cust_id,
            "timestamp": timestamp.isoformat(timespec="seconds"),
            "amount": amount,
            "currency": random.choice(settings.CURRENCIES),
            "country": country,
            "merchant_id": merchant["merchant_id"],
            "merchant_name": merchant["merchant_name"],
            "payment_type": random.choices(
                PAYMENT_TYPES, weights=[15, 35, 10, 20, 8, 12])[0],
            "account_type": random.choice(ACCOUNT_TYPES),
            "direction": direction,
            "device_id": f"DEV{random.randint(1000, 9999)}",
            "ip_address": f"{random.randint(1,223)}.{random.randint(0,255)}."
                           f"{random.randint(0,255)}.{random.randint(1,254)}",
            "channel": random.choice(CHANNELS),
            "risk_country_flag": country in settings.HIGH_RISK_COUNTRIES,
            "description": f"{merchant['category']} transaction via {merchant['merchant_name']}",
        })

    df = pd.DataFrame(rows)

    # Force in explicit structuring bursts: 3-4 sub-threshold cash/wire deposits
    # from the same customer within a 24h window (classic smurfing pattern)
    burst_rows = []
    for cust_id in structuring_customers:
        burst_day = now - timedelta(days=random.randint(1, 150))
        for j in range(random.randint(3, 4)):
            burst_rows.append({
                "transaction_id": f"TS{cust_id}{j}",
                "customer_id": cust_id,
                "timestamp": (burst_day + timedelta(hours=j * 3)).isoformat(timespec="seconds"),
                "amount": round(random.uniform(9000, 9950), 2),
                "currency": "USD",
                "country": customer_lookup.loc[cust_id, "country"],
                "merchant_id": merchants.sample(1).iloc[0]["merchant_id"],
                "merchant_name": merchants.sample(1).iloc[0]["merchant_name"],
                "payment_type": random.choice(["Cash Deposit", "Wire Transfer"]),
                "account_type": "Current",
                "direction": "Incoming",
                "device_id": f"DEV{random.randint(1000, 9999)}",
                "ip_address": f"{random.randint(1,223)}.0.0.{random.randint(1,254)}",
                "channel": random.choice(["Branch", "Online"]),
                "risk_country_flag": False,
                "description": "Sub-threshold deposit",
            })

    # Force in explicit rapid-movement bursts (>=3 outgoing txns within an hour)
    for cust_id in rapid_movement_customers:
        burst_time = now - timedelta(days=random.randint(1, 30))
        for j in range(random.randint(3, 5)):
            burst_rows.append({
                "transaction_id": f"TB{cust_id}{j}",
                "customer_id": cust_id,
                "timestamp": (burst_time + timedelta(minutes=j * 7)).isoformat(timespec="seconds"),
                "amount": round(random.uniform(2000, 8000), 2),
                "currency": "USD",
                "country": customer_lookup.loc[cust_id, "country"],
                "merchant_id": merchants.sample(1).iloc[0]["merchant_id"],
                "merchant_name": merchants.sample(1).iloc[0]["merchant_name"],
                "payment_type": "Wire Transfer",
                "account_type": "Current",
                "direction": "Outgoing",
                "device_id": f"DEV{random.randint(1000, 9999)}",
                "ip_address": f"{random.randint(1,223)}.0.0.{random.randint(1,254)}",
                "channel": "Online",
                "risk_country_flag": False,
                "description": "Rapid outgoing wire transfer",
            })

    # Force in explicit high-velocity days for a subset of customers
    for cust_id in high_velocity_customers:
        v_day = now - timedelta(days=random.randint(1, 60))
        for j in range(random.randint(12, 20)):
            burst_rows.append({
                "transaction_id": f"TV{cust_id}{j}",
                "customer_id": cust_id,
                "timestamp": (v_day + timedelta(minutes=j * 15)).isoformat(timespec="seconds"),
                "amount": round(random.uniform(50, 500), 2),
                "currency": "USD",
                "country": customer_lookup.loc[cust_id, "country"],
                "merchant_id": merchants.sample(1).iloc[0]["merchant_id"],
                "merchant_name": merchants.sample(1).iloc[0]["merchant_name"],
                "payment_type": "Card Payment",
                "account_type": "Current",
                "direction": "Outgoing",
                "device_id": f"DEV{random.randint(1000, 9999)}",
                "ip_address": f"{random.randint(1,223)}.0.0.{random.randint(1,254)}",
                "channel": "Mobile App",
                "risk_country_flag": False,
                "description": "High frequency card spend",
            })

    df = pd.concat([df, pd.DataFrame(burst_rows)], ignore_index=True)
    df = df.sort_values("timestamp").reset_index(drop=True)

    log_event("DATA_GENERATION", f"Generated {len(df)} transactions")
    return df


def generate_all(save=True):
    merchants = generate_merchants()
    customers = generate_customers()
    transactions = generate_transactions(customers, merchants)

    if save:
        os.makedirs(settings.DATA_RAW, exist_ok=True)
        merchants.to_csv(os.path.join(settings.DATA_RAW, "merchants.csv"), index=False)
        customers.to_csv(os.path.join(settings.DATA_RAW, "customers.csv"), index=False)
        transactions.to_csv(os.path.join(settings.DATA_RAW, "transactions.csv"), index=False)
        log_event("DATA_GENERATION", "Saved raw datasets to data/raw/")

    return customers, merchants, transactions


if __name__ == "__main__":
    generate_all()
