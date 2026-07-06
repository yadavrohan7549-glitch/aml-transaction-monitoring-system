"""
Step 10 - Static professional charts (PNG) for reports/README.

The Streamlit dashboard uses interactive Plotly charts (see
dashboard/app.py); this module produces static matplotlib exports that
can be embedded in Word/PDF reports or the README/portfolio.
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.config import settings
from src.logger import log_event

plt.rcParams.update({"figure.dpi": 120, "axes.titleweight": "bold"})
COLOR = "#1F4E78"


def _save(fig, name):
    os.makedirs(settings.CHARTS_DIR, exist_ok=True)
    path = os.path.join(settings.CHARTS_DIR, name)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    log_event("CHARTS", f"Saved chart {name}")


def chart_risk_distribution(risk_scores: pd.DataFrame):
    counts = risk_scores["risk_band"].value_counts().reindex(
        ["Low", "Medium", "High", "Critical"]).fillna(0)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(counts.index, counts.values, color=["#4C9A5B", "#E8B84B", "#D9782D", "#C0392B"])
    ax.set_title("Customer Risk Distribution")
    ax.set_ylabel("Number of Customers")
    _save(fig, "risk_distribution.png")


def chart_alerts_by_rule(alerts: pd.DataFrame):
    counts = alerts["rule_name"].value_counts().sort_values()
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(counts.index, counts.values, color=COLOR)
    ax.set_title("Alerts by Rule Type")
    ax.set_xlabel("Alert Count")
    _save(fig, "alerts_by_rule.png")


def chart_country_distribution(transactions: pd.DataFrame):
    counts = transactions["country"].value_counts().head(10)
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.bar(counts.index, counts.values, color=COLOR)
    ax.set_title("Top 10 Countries by Transaction Count")
    plt.xticks(rotation=45, ha="right")
    _save(fig, "country_distribution.png")


def chart_transaction_trend(transactions: pd.DataFrame):
    daily = transactions.assign(day=transactions["timestamp"].dt.date).groupby("day")["amount_usd"].sum()
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(list(daily.index), daily.values, color=COLOR)
    ax.set_title("Daily Transaction Volume (USD)")
    ax.set_ylabel("USD")
    _save(fig, "transaction_trend.png")


def chart_alert_trend(alerts: pd.DataFrame, transactions: pd.DataFrame):
    merged = alerts.merge(transactions[["transaction_id", "timestamp"]], on="transaction_id", how="left")
    merged["day"] = pd.to_datetime(merged["timestamp"]).dt.date
    daily = merged.groupby("day").size()
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(list(daily.index), daily.values, color="#C0392B")
    ax.set_title("Daily Alert Volume")
    ax.set_ylabel("Alerts")
    _save(fig, "alert_trend.png")


def chart_monthly_volume(transactions: pd.DataFrame):
    monthly = transactions.assign(
        month=transactions["timestamp"].dt.to_period("M").astype(str)
    ).groupby("month")["amount_usd"].sum()
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(monthly.index, monthly.values, color=COLOR)
    ax.set_title("Monthly Transaction Volume (USD)")
    plt.xticks(rotation=45, ha="right")
    _save(fig, "monthly_volume.png")


def chart_customer_segmentation(customers: pd.DataFrame):
    counts = customers["customer_type"].value_counts()
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.pie(counts.values, labels=counts.index, autopct="%1.0f%%",
           colors=["#1F4E78", "#4C9A5B", "#E8B84B"])
    ax.set_title("Customer Segmentation")
    _save(fig, "customer_segmentation.png")


def chart_merchant_analysis(transactions: pd.DataFrame):
    counts = transactions.groupby("merchant_name")["amount_usd"].sum().sort_values(ascending=False).head(10)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(counts.index[::-1], counts.values[::-1], color=COLOR)
    ax.set_title("Top 10 Merchants by Flow (USD)")
    _save(fig, "merchant_analysis.png")


def chart_payment_type_pie(transactions: pd.DataFrame):
    counts = transactions["payment_type"].value_counts()
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.pie(counts.values, labels=counts.index, autopct="%1.0f%%")
    ax.set_title("Payment Type Distribution")
    _save(fig, "payment_type_distribution.png")


def chart_amount_scatter(transactions: pd.DataFrame):
    sample = transactions.sample(min(1500, len(transactions)), random_state=42)
    fig, ax = plt.subplots(figsize=(7, 5))
    colors = sample["is_anomaly"].map({True: "#C0392B", False: "#1F4E78"}) \
        if "is_anomaly" in sample.columns else COLOR
    ax.scatter(sample["timestamp"], sample["amount_usd"], c=colors, s=8, alpha=0.6)
    ax.set_title("Transaction Amounts Over Time (red = ML anomaly)")
    ax.set_ylabel("USD")
    _save(fig, "amount_scatter.png")


def generate_all_charts(customers, transactions, alerts, risk_scores):
    chart_risk_distribution(risk_scores)
    chart_alerts_by_rule(alerts)
    chart_country_distribution(transactions)
    chart_transaction_trend(transactions)
    chart_alert_trend(alerts, transactions)
    chart_monthly_volume(transactions)
    chart_customer_segmentation(customers)
    chart_merchant_analysis(transactions)
    chart_payment_type_pie(transactions)
    chart_amount_scatter(transactions)
    log_event("CHARTS", "All charts generated successfully")
