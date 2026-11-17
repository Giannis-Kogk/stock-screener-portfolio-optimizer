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

# load the full screening universe (92 stocks) ---
@st.cache_data
def load_universe() -> pd.DataFrame:
    """All stocks that passed data cleaning (excluded = 0) with their four ratios.

    Unlike screen_results (35 stocks, one fixed rule), this is the raw
    universe, so the user can apply any thresholds on top of it.
    """
    query = """
        SELECT c.ticker, c.name, c.sector,
               f.pe, f.pb, f.roe, f.peg_ratio
        FROM companies c
        JOIN fundamentals f ON f.ticker = c.ticker
        JOIN data_quality d ON d.ticker = c.ticker
        WHERE d.excluded = 0          -- drop the 17 flagged stocks
    """
    conn = sqlite3.connect(DB_PATH)   # new connection per call, same reason as in load_table
    try:
        return pd.read_sql_query(query, conn)
    finally:
        conn.close()


# --- Screening results (35 stocks chosen on Day 5) ---
screen = load_table("SELECT * FROM screen_results ORDER BY score DESC, ticker")

st.subheader("Screened stocks")
st.metric("Stocks in screen_results", len(screen))  # a big number with a label

# Count of stocks per sector, to cross-check against the plan (24 IT, 11 Consumer Staples)
st.write(screen["sector"].value_counts())

st.dataframe(screen)  # interactive table: sortable columns

# --- Day 9, Step 1: temporary check of the universe ---
universe = load_universe()

# --- Day 9, Step 2: adjustable absolute screening criteria ---
st.sidebar.header("Screening criteria")
st.sidebar.caption("Absolute limits, applied to the 92 stocks that passed data cleaning.")

# Each slider returns a plain number; the defaults are the Day 5 limits
max_pe = st.sidebar.slider("Max P/E", min_value=5.0, max_value=100.0, value=25.0, step=1.0)
max_pb = st.sidebar.slider("Max P/B", min_value=0.5, max_value=20.0, value=3.0, step=0.5)
min_roe_pct = st.sidebar.slider("Min ROE (%)", min_value=0, max_value=100, value=15, step=1)
max_peg = st.sidebar.slider("Max PEG", min_value=0.1, max_value=5.0, value=1.5, step=0.1)

min_roe = min_roe_pct / 100  # roe is stored as a fraction (0.15 = 15%), so convert from percent

# --- Day 9, Step 3: sector filter + rejection reasons ---
sectors = sorted(universe["sector"].unique())   # ["Consumer Staples", "Information Technology"]
chosen_sectors = st.sidebar.multiselect("Sectors", options=sectors, default=sectors)

# Work on the chosen sectors only; .copy() because we add a column below
scope = universe[universe["sector"].isin(chosen_sectors)].copy()

# One boolean column per criterion: True means the stock FAILS that criterion
fail = pd.DataFrame({
    "P/E": scope["pe"] > max_pe,
    "P/B": scope["pb"] > max_pb,
    "ROE": scope["roe"] < min_roe,
    "PEG": scope["peg_ratio"] > max_peg,
})

# For each row, join the names of the failed criteria: "P/E, PEG" (empty text = passed)
scope["reasons"] = [", ".join(fail.columns[row]) for row in fail.to_numpy()]

# Number of failed criteria per stock: True counts as 1, False as 0, summed across the row (axis=1)
scope["n_failed"] = fail.sum(axis=1)

passed = scope["reasons"] == ""   # no failed criterion at all
result = scope[passed]            # stocks passing every criterion
# Fewest failures first (the "almost passed" stocks); ticker breaks ties alphabetically
rejected = scope[~passed].sort_values(["n_failed", "ticker"])

st.subheader("Stocks passing the criteria")
st.metric("Stocks passing all criteria", len(result))
st.dataframe(result.drop(columns=["reasons", "n_failed"]))   # both columns are meaningless for passed stocks

with st.expander(f"Rejected stocks and why ({len(rejected)})"):
    st.dataframe(rejected)

# --- Optimised portfolios (precomputed by src/optimize.py, so the app only reads them) ---
summary = load_table("SELECT * FROM portfolio_summary")
weights = load_table("SELECT portfolio, ticker, weight FROM optimal_weights")

st.subheader("Portfolio comparison")

# Tell the reader that the sliders above do NOT drive this section
st.info(
    "The portfolio weights below are precomputed for a fixed set of 35 stocks "
    "(relative screening, score >= 3). They do not change with the sliders above."
)

st.dataframe(summary)   # includes rf, max_weight and data_end_date, so the assumptions are visible

choice = st.selectbox("Portfolio", summary["portfolio"])   # returns the selected name as a string

# Keep only the chosen portfolio and the stocks that actually have a position (weight > 0.1%)
held = weights[(weights["portfolio"] == choice) & (weights["weight"] > 0.001)]
held = held.sort_values("weight", ascending=False)

st.metric("Stocks held", len(held))
st.dataframe(held[["ticker", "weight"]].round(4))

