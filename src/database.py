"""
Step 11 - SQLite persistence layer.

Creates and populates: customers, transactions, merchants, countries,
alerts, cases, risk_scores, audit_logs.
"""

import os
import sqlite3

import pandas as pd

from src.config import settings
from src.logger import log_event


def get_connection() -> sqlite3.Connection:
    os.makedirs(settings.DATABASE_DIR, exist_ok=True)
    return sqlite3.connect(settings.DB_PATH)


def initialize_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            message TEXT,
            event_time TEXT
        );
        CREATE TABLE IF NOT EXISTS countries (
            country TEXT PRIMARY KEY,
            risk_category TEXT
        );
    """)
    conn.commit()


def build_countries_table(conn: sqlite3.Connection) -> None:
    rows = []
    for c in settings.HIGH_RISK_COUNTRIES:
        rows.append((c, "High"))
    for c in settings.MEDIUM_RISK_COUNTRIES:
        rows.append((c, "Medium"))
    for c in settings.LOW_RISK_COUNTRIES:
        rows.append((c, "Low"))
    conn.executemany("INSERT OR REPLACE INTO countries (country, risk_category) VALUES (?, ?)", rows)
    conn.commit()


def save_dataframe(conn: sqlite3.Connection, df: pd.DataFrame, table_name: str) -> None:
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    log_event("DATABASE", f"Wrote {len(df)} rows to table '{table_name}'")


def persist_all(customers, transactions, merchants, alerts, cases, risk_scores) -> None:
    conn = get_connection()
    initialize_schema(conn)
    build_countries_table(conn)

    save_dataframe(conn, customers, "customers")
    save_dataframe(conn, transactions, "transactions")
    save_dataframe(conn, merchants, "merchants")
    save_dataframe(conn, alerts, "alerts")
    save_dataframe(conn, cases, "cases")
    save_dataframe(conn, risk_scores, "risk_scores")

    conn.close()
    log_event("DATABASE", f"All tables persisted to {settings.DB_PATH}")
