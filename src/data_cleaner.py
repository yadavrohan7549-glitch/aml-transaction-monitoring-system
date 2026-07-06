"""
Step 3 - Data cleaning & validation.

Every cleaning action is counted and logged so the pipeline produces an
auditable data-quality trail, the way a real bank's data governance
team would expect.
"""

import pandas as pd

from src.logger import log_event

FX_TO_USD = {
    "USD": 1.0, "EUR": 1.08, "GBP": 1.27, "INR": 0.012,
    "AED": 0.27, "SGD": 0.74, "JPY": 0.0068, "CHF": 1.13,
}


def clean_customers(df: pd.DataFrame) -> pd.DataFrame:
    before = len(df)
    df = df.drop_duplicates(subset="customer_id").copy()
    df["name"] = df["name"].str.strip().str.title()
    df["country"] = df["country"].str.strip()
    df["income"] = pd.to_numeric(df["income"], errors="coerce").fillna(df["income"].median())
    df["dob"] = pd.to_datetime(df["dob"], errors="coerce")
    df = df.dropna(subset=["dob"])
    removed = before - len(df)
    log_event("DATA_CLEANING", f"Customers: removed {removed} duplicate/invalid rows, "
                                f"{len(df)} remain")
    return df


def clean_transactions(df: pd.DataFrame) -> pd.DataFrame:
    before = len(df)
    df = df.drop_duplicates(subset="transaction_id").copy()

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"])

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df = df.dropna(subset=["amount"])
    df = df[df["amount"] > 0]

    df["merchant_name"] = df["merchant_name"].fillna("Unknown Merchant").str.strip()
    df["country"] = df["country"].fillna("Unknown").str.strip()
    df["description"] = df["description"].fillna("")

    # Normalise currency into a USD-equivalent column for cross-currency rules
    df["amount_usd"] = df.apply(
        lambda r: round(r["amount"] * FX_TO_USD.get(r["currency"], 1.0), 2), axis=1
    )

    removed = before - len(df)
    log_event("DATA_CLEANING", f"Transactions: removed {removed} duplicate/invalid rows, "
                                f"{len(df)} remain")
    return df.sort_values("timestamp").reset_index(drop=True)


def run_cleaning(customers: pd.DataFrame, transactions: pd.DataFrame):
    clean_c = clean_customers(customers)
    clean_t = clean_transactions(transactions)
    # drop transactions whose customer no longer exists post-cleaning
    valid_ids = set(clean_c["customer_id"])
    before = len(clean_t)
    clean_t = clean_t[clean_t["customer_id"].isin(valid_ids)]
    if before - len(clean_t):
        log_event("DATA_CLEANING",
                  f"Dropped {before - len(clean_t)} transactions with orphaned customer_id")
    return clean_c, clean_t
