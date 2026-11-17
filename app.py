import streamlit as st
import sqlite3
from pathlib import Path

import pandas as pd

# Build the DB path relative to THIS file, so it works locally and on Streamlit Cloud
DB_PATH = Path(__file__).parent / "data" / "portfolio.db"

# Page settings must be the FIRST Streamlit call in the script
st.set_page_config(
    page_title="Stock Screener & Portfolio Optimizer",
    layout="wide",  # use the full browser width instead of a narrow centered column
)

st.title("Stock Screener & Portfolio Optimizer")
st.caption("US market · Python · SQLite · Streamlit")

@st.cache_data  # result is stored per unique `query` string; the function body runs only on a cache miss
def load_table(query: str) -> pd.DataFrame:
    # A new connection per call: Streamlit runs the script in different threads,
    # and a sqlite3 connection can only be used in the thread that created it
    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query(query, conn)  # run the SQL and return a DataFrame
    finally:
        conn.close()  # always close, even if the query raises an error


# --- Screening results (35 stocks chosen on Day 5) ---
screen = load_table("SELECT * FROM screen_results ORDER BY score DESC, ticker")

st.subheader("Screened stocks")
st.metric("Stocks in screen_results", len(screen))  # a big number with a label

# Count of stocks per sector, to cross-check against the plan (24 IT, 11 Consumer Staples)
st.write(screen["sector"].value_counts())

st.dataframe(screen)  # interactive table: sortable columns

# --- Optimised portfolios (precomputed by src/optimize.py, so the app only reads them) ---
summary = load_table("SELECT * FROM portfolio_summary")
weights = load_table("SELECT portfolio, ticker, weight FROM optimal_weights")

st.subheader("Portfolio comparison")
st.dataframe(summary)   # includes rf, max_weight and data_end_date, so the assumptions are visible

choice = st.selectbox("Portfolio", summary["portfolio"])   # returns the selected name as a string

# Keep only the chosen portfolio and the stocks that actually have a position (weight > 0.1%)
held = weights[(weights["portfolio"] == choice) & (weights["weight"] > 0.001)]
held = held.sort_values("weight", ascending=False)

st.metric("Stocks held", len(held))
st.dataframe(held[["ticker", "weight"]].round(4))

