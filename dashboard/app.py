"""
Step 8 - Streamlit dashboard.

Run with:  streamlit run dashboard/app.py

Requires main.py to have been run at least once so database/aml_system.db exists.
"""

import os
import sys

import pandas as pd
import plotly.express as px
import sqlite3
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import settings  # noqa: E402
from src.logger import log_event  # noqa: E402

st.set_page_config(page_title="AML Transaction Monitoring", layout="wide", page_icon="🛡️")


@st.cache_data(ttl=60)
def load_data():
    conn = sqlite3.connect(settings.DB_PATH)
    customers = pd.read_sql("SELECT * FROM customers", conn)
    transactions = pd.read_sql("SELECT * FROM transactions", conn)
    alerts = pd.read_sql("SELECT * FROM alerts", conn)
    cases = pd.read_sql("SELECT * FROM cases", conn)
    risk_scores = pd.read_sql("SELECT * FROM risk_scores", conn)
    conn.close()
    transactions["timestamp"] = pd.to_datetime(transactions["timestamp"])
    return customers, transactions, alerts, cases, risk_scores


if not os.path.exists(settings.DB_PATH):
    st.error("No database found. Run `python main.py` first to generate data.")
    st.stop()

customers, transactions, alerts, cases, risk_scores = load_data()
log_event("DASHBOARD", "Dashboard accessed")

st.title("🛡️ AML Transaction Monitoring Dashboard")
st.caption("Internal compliance tool - synthetic data only")

tabs = st.tabs(["Executive Summary", "Alerts", "Risk & Customers",
                "Cases", "Charts", "Search"])

# ---------------------------------------------------------------------------
# Executive Summary
# ---------------------------------------------------------------------------
with tabs[0]:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Transactions", f"{len(transactions):,}")
    c2.metric("Total Customers", f"{len(customers):,}")
    c3.metric("Total Alerts", f"{len(alerts):,}")
    c4.metric("High Risk Customers", int((risk_scores["risk_band"] == "High").sum()))
    c5.metric("Critical Alerts", int((alerts["priority"] == "High").sum()))

    col1, col2 = st.columns(2)
    with col1:
        band_counts = risk_scores["risk_band"].value_counts().reindex(
            ["Low", "Medium", "High", "Critical"]).fillna(0)
        fig = px.bar(x=band_counts.index, y=band_counts.values,
                     labels={"x": "Risk Band", "y": "Customers"},
                     title="Risk Distribution", color=band_counts.index,
                     color_discrete_sequence=["#4C9A5B", "#E8B84B", "#D9782D", "#C0392B"])
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        daily = transactions.assign(day=transactions["timestamp"].dt.date) \
            .groupby("day")["amount_usd"].sum().reset_index()
        fig = px.line(daily, x="day", y="amount_usd", title="Daily Transaction Volume (USD)")
        st.plotly_chart(fig, use_container_width=True)

    country_counts = transactions["country"].value_counts().reset_index()
    country_counts.columns = ["country", "transactions"]
    fig = px.choropleth(country_counts, locations="country", locationmode="country names",
                         color="transactions", title="Transaction Country Heatmap",
                         color_continuous_scale="Reds")
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------
with tabs[1]:
    st.subheader("Recent Alerts")
    rule_filter = st.multiselect("Filter by rule", sorted(alerts["rule_name"].unique()))
    priority_filter = st.multiselect("Filter by priority", sorted(alerts["priority"].unique()))

    filtered = alerts.copy()

if rule_filter:
    filtered = filtered[filtered["rule_name"].isin(rule_filter)]

if priority_filter:
    filtered = filtered[filtered["priority"].isin(priority_filter)]

st.dataframe(filtered.sort_values("risk_score", ascending=False),
             use_container_width=True, height=400)

rule_counts = (
    alerts["rule_name"]
    .value_counts()
    .rename_axis("rule_name")
    .reset_index(name="count")
)

fig = px.bar(
    rule_counts,
    x="rule_name",
    y="count",
    title="Alerts by Rule"
)
st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Risk & Customers
# ---------------------------------------------------------------------------
with tabs[2]:
    st.subheader("Top Risky Customers")
    merged = customers.merge(risk_scores, on="customer_id", how="left")
    top_customers = merged.sort_values("risk_score", ascending=False).head(25)
    st.dataframe(
        top_customers[["customer_id", "name", "country", "risk_score", "risk_band",
                       "contributing_factors", "total_alerts"]],
        use_container_width=True, height=400,
    )

    st.subheader("Top Risky Merchants")
    merchant_risk = transactions.merge(alerts, on="transaction_id", how="inner")
    top_merchants = merchant_risk.groupby("merchant_name").size().sort_values(
        ascending=False).head(10).reset_index(name="alert_count")
    st.dataframe(top_merchants, use_container_width=True)

# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------
with tabs[3]:
    st.subheader("Investigation Case Queue")
    status_filter = st.multiselect("Filter by status", sorted(cases["status"].unique()))
    case_view = cases.copy()
    if status_filter:
        case_view = case_view[case_view["status"].isin(status_filter)]
    st.dataframe(case_view.sort_values("risk_score", ascending=False),
                 use_container_width=True, height=450)

# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
with tabs[4]:
    st.subheader("Transaction Trends")
    monthly = transactions.assign(
        month=transactions["timestamp"].dt.to_period("M").astype(str)
    ).groupby("month")["amount_usd"].sum().reset_index()
    st.plotly_chart(px.bar(monthly, x="month", y="amount_usd", title="Monthly Volume (USD)"),
                     use_container_width=True)

    seg = customers["customer_type"].value_counts().reset_index()
    seg.columns = ["customer_type", "count"]
    st.plotly_chart(px.pie(seg, names="customer_type", values="count", title="Customer Segmentation"),
                     use_container_width=True)

    pay = transactions["payment_type"].value_counts().reset_index()
    pay.columns = ["payment_type", "count"]
    st.plotly_chart(px.pie(pay, names="payment_type", values="count", title="Payment Type Mix"),
                     use_container_width=True)

    st.plotly_chart(
        px.scatter(transactions.sample(min(2000, len(transactions))),
                   x="timestamp", y="amount_usd", color="is_anomaly",
                   title="Transaction Amounts (colored by ML anomaly flag)"),
        use_container_width=True,
    )

# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
with tabs[5]:
    st.subheader("Customer Search")
    query = st.text_input("Search by customer ID or name")
    if query:
        results = customers[
            customers["customer_id"].str.contains(query, case=False, na=False) |
            customers["name"].str.contains(query, case=False, na=False)
        ]
        st.dataframe(results, use_container_width=True)
        if len(results) == 1:
            cust_id = results.iloc[0]["customer_id"]
            st.write("Transaction history:")
            st.dataframe(transactions[transactions["customer_id"] == cust_id]
                         .sort_values("timestamp", ascending=False), use_container_width=True)

    st.subheader("Case Search")
    case_query = st.text_input("Search by case number or customer ID")
    if case_query:
        case_results = cases[
            cases["case_number"].str.contains(case_query, case=False, na=False) |
            cases["customer_id"].str.contains(case_query, case=False, na=False)
        ]
        st.dataframe(case_results, use_container_width=True)
