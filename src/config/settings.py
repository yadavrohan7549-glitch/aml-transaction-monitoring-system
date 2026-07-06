"""
Central configuration for the AML Transaction Monitoring System.
Keeping all tunables in one place makes the rule engine and scoring
model easy to defend / explain in an interview.
"""

import os

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATA_RAW = os.path.join(ROOT_DIR, "data", "raw")
DATA_PROCESSED = os.path.join(ROOT_DIR, "data", "processed")
DATA_GENERATED = os.path.join(ROOT_DIR, "data", "generated")
DATABASE_DIR = os.path.join(ROOT_DIR, "database")
MODELS_DIR = os.path.join(ROOT_DIR, "models")
REPORTS_DIR = os.path.join(ROOT_DIR, "reports")
CHARTS_DIR = os.path.join(ROOT_DIR, "charts")
LOGS_DIR = os.path.join(ROOT_DIR, "data", "generated")

DB_PATH = os.path.join(DATABASE_DIR, "aml_system.db")

# ---------------------------------------------------------------------------
# Data generation volumes
# ---------------------------------------------------------------------------
NUM_CUSTOMERS = 500
NUM_MERCHANTS = 50
NUM_TRANSACTIONS = 10_000
RANDOM_SEED = 42

# ---------------------------------------------------------------------------
# Country risk classification (used by multiple rules)
# ---------------------------------------------------------------------------
HIGH_RISK_COUNTRIES = [
    "Iran", "North Korea", "Syria", "Myanmar", "Afghanistan",
    "Yemen", "South Sudan", "Venezuela", "Democratic Republic of Congo",
]

MEDIUM_RISK_COUNTRIES = [
    "Russia", "Pakistan", "Nigeria", "UAE", "Turkey", "Philippines",
]

LOW_RISK_COUNTRIES = [
    "United Kingdom", "United States", "Germany", "France", "India",
    "Canada", "Australia", "Singapore", "Japan", "Netherlands",
    "Ireland", "Sweden", "Switzerland", "Spain", "Italy",
]

ALL_COUNTRIES = HIGH_RISK_COUNTRIES + MEDIUM_RISK_COUNTRIES + LOW_RISK_COUNTRIES

CURRENCIES = ["USD", "EUR", "GBP", "INR", "AED", "SGD", "JPY", "CHF"]

# ---------------------------------------------------------------------------
# Rule thresholds - deliberately explicit and documented, mirrors how a
# real transaction monitoring system's parameter register would look.
# ---------------------------------------------------------------------------
LARGE_CASH_THRESHOLD = 10_000          # CTR-style threshold
STRUCTURING_THRESHOLD = 10_000         # Reporting threshold being avoided
STRUCTURING_WINDOW_HOURS = 24
STRUCTURING_MIN_COUNT = 3
JUST_BELOW_THRESHOLD_PCT = 0.90        # 90-99% of reporting threshold
RAPID_MOVEMENT_WINDOW_MINUTES = 60
RAPID_MOVEMENT_MIN_COUNT = 3
VELOCITY_WINDOW_HOURS = 24
VELOCITY_MULTIPLIER = 3                # x times the customer's normal daily count
DORMANCY_DAYS = 90
VOLUME_SPIKE_MULTIPLIER = 5
ROUND_AMOUNT_MODULO = 1000
MULTI_COUNTRY_WINDOW_HOURS = 24
MULTI_COUNTRY_MIN_COUNT = 3
SAME_BENEFICIARY_MIN_SENDERS = 4
SAME_BENEFICIARY_WINDOW_HOURS = 48

# ---------------------------------------------------------------------------
# Risk scoring weights (0-100 point weighted model)
# ---------------------------------------------------------------------------
RISK_WEIGHTS = {
    "pep": 20,
    "sanction": 40,
    "high_risk_country": 15,
    "structuring": 15,
    "high_velocity": 10,
    "large_cash": 10,
    "dormant_reactivation": 10,
    "previous_alerts": 10,
    "anomaly_ml": 15,
}

RISK_BANDS = [
    (0, 20, "Low"),
    (20, 45, "Medium"),
    (45, 70, "High"),
    (70, 1000, "Critical"),
]
