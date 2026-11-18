import streamlit as st
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go  # plotly figures for the charts

# Build the DB path relative to THIS file, so it works locally and on Streamlit Cloud
DB_PATH = Path(__file__).parent / "data" / "portfolio.db"

# One fixed colour per portfolio, so the same portfolio looks the same in every chart
PORTFOLIO_COLORS = {
    "equal_weight": "#F5A524",
    "min_variance": "#2DD4BF",
    "max_sharpe": "#A78BFA",
}

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


def frontier_figure(frontier: pd.DataFrame, summary: pd.DataFrame, cloud: pd.DataFrame) -> go.Figure:
    """Build the efficient-frontier chart.

    frontier: columns ann_vol, ann_return (40 points, fractions e.g. 0.0962)
    summary:  one row per portfolio, columns portfolio, ann_vol, ann_return, sharpe, rf
    cloud:    columns ann_vol, ann_return (random long-only portfolios, drawn FIRST = behind everything)
    """
    fig = go.Figure()

    # Sharpe ratio of every random portfolio, with the same risk-free rate the optimiser used
    rf = float(summary["rf"].iloc[0])
    cloud_sharpe = (cloud["ann_return"] - rf) / cloud["ann_vol"]

    # Random portfolios: the feasible region, coloured by Sharpe ratio.
    # Plain go.Scatter (SVG), NOT Scattergl: WebGL traces are painted ABOVE all SVG traces,
    # so they would hide the portfolio markers and labels whatever the trace order is.
    # hoverinfo="skip" removes their tooltips so hovering only reacts to the points that matter
    fig.add_trace(go.Scatter(
        x=cloud["ann_vol"],
        y=cloud["ann_return"],
        mode="markers",
        name=f"Random ({len(cloud):,}): greener = higher Sharpe",
        marker=dict(
            size=3,
            color=cloud_sharpe,                                    # one number per point -> colour scale
            colorscale=[[0, "#475569"], [1, "#A3E635"]],           # dark slate (low Sharpe) -> lime (high Sharpe)
            opacity=0.45,                                          # transparent: dense areas look stronger
            showscale=False,                                       # the legend text explains the colours
        ),
        hoverinfo="skip",
    ))

    # The frontier: a line PLUS small dots, so the reader sees these are 40 solved points
    # (the straight segments between the dots are only a visual connection)
    fig.add_trace(go.Scatter(
        x=frontier["ann_vol"],
        y=frontier["ann_return"],
        mode="lines+markers",
        name="Efficient frontier",
        line=dict(color="#4F8EF7", width=2),   # same accent colour as the theme
        marker=dict(size=4),
        # %{x:.1%} formats 0.139 as 13.9%; <extra> sets the small label next to the tooltip
        hovertemplate="Volatility: %{x:.1%}<br>Return: %{y:.1%}<extra>Frontier</extra>",
    ))

    # One marker per portfolio (label comes from the database, not hard-coded)
    for _, row in summary.iterrows():
        name = str(row["portfolio"])
        fig.add_trace(go.Scatter(
            x=[row["ann_vol"]],
            y=[row["ann_return"]],
            mode="markers+text",                       # marker plus a text label next to it
            name=name,
            text=[name],
            textposition="middle right",
            textfont=dict(size=11),
            marker=dict(
                size=13,
                color=PORTFOLIO_COLORS.get(name),
                line=dict(width=1.5, color="#0E1117"),  # thin outline in the page colour, separates marker from line
            ),
            customdata=[[row["sharpe"]]],              # extra value available inside hovertemplate
            hovertemplate=(
                "Volatility: %{x:.1%}<br>Return: %{y:.1%}"
                "<br>Sharpe: %{customdata[0]:.2f}<extra>" + name + "</extra>"
            ),
        ))

    grid = "rgba(255,255,255,0.08)"                    # faint grid lines on the dark background
    fig.update_layout(
        template="plotly_dark",                        # dark axes, grid and fonts
        paper_bgcolor="rgba(0,0,0,0)",                 # transparent: page background shows through
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(title="Annualised volatility (risk)", tickformat=".0%",
                   dtick=0.05, gridcolor=grid, zeroline=False),   # a grid line every 5 percentage points
        yaxis=dict(title="Annualised return", tickformat=".0%",
                   dtick=0.05, gridcolor=grid, zeroline=False),
       legend=dict(
            orientation="h",
            yref="container",   # anchor to the whole figure, not to the plot area
            y=1, yanchor="top",
            xanchor="left", x=0,
        ),
        margin=dict(l=10, r=10, t=100, b=10),  # t reserves room for up to 5 legend rows           # t=90 leaves room for up to three legend rows
        hovermode="closest",                           # tooltip of the nearest point, not of everything at the same x
    )
    return fig

def weights_figure(held: pd.DataFrame, color: str) -> go.Figure:
    """Horizontal bar chart of the held positions of ONE portfolio.

    held:  columns ticker, weight (fractions, e.g. 0.15)
    color: bar colour, taken from PORTFOLIO_COLORS
    """
    # Plotly draws the FIRST category at the bottom, so sort ascending
    # to get the largest weight at the top of the chart
    data = held.sort_values("weight", ascending=True)

    fig = go.Figure(go.Bar(
        x=data["weight"],
        y=data["ticker"],
        orientation="h",                                  # horizontal bars
        marker=dict(color=color),
        hovertemplate="%{y}: %{x:.1%}<extra></extra>",    # "MU: 15.0%"; <extra> removes the side label
    ))

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(title="Portfolio weight", tickformat=".0%"),
        yaxis=dict(title=None, type="category"),          # tickers are text: treat them as categories
        height=max(300, 22 * len(data) + 80),             # grow with the number of bars (equal_weight has 35)
        margin=dict(l=10, r=10, t=10, b=10),
    )
    return fig


# --- Sidebar: adjustable absolute screening criteria (Day 9) ---
universe = load_universe()

st.sidebar.header("Screening criteria")
st.sidebar.caption("Absolute limits, applied to the 92 stocks that passed data cleaning.")

# Each slider returns a plain number; the defaults are the Day 5 limits
max_pe = st.sidebar.slider("Max P/E", min_value=5.0, max_value=100.0, value=25.0, step=1.0)
max_pb = st.sidebar.slider("Max P/B", min_value=0.5, max_value=20.0, value=3.0, step=0.5)
min_roe_pct = st.sidebar.slider("Min ROE (%)", min_value=0, max_value=100, value=15, step=1)
max_peg = st.sidebar.slider("Max PEG", min_value=0.1, max_value=5.0, value=1.5, step=0.1)

min_roe = min_roe_pct / 100  # roe is stored as a fraction (0.15 = 15%), so convert from percent

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


# --- Day 10: two tabs. Everything above only computes; the tabs only display. ---
tab_screen, tab_port = st.tabs(["Screening", "Portfolios"])

with tab_screen:
    st.subheader("Stocks passing the criteria")
    st.metric("Stocks passing all criteria", len(result))
    st.dataframe(result.drop(columns=["reasons", "n_failed"]))   # both columns are meaningless for passed stocks

    with st.expander(f"Rejected stocks and why ({len(rejected)})"):
        st.dataframe(rejected)

with tab_port:
    # Optimised portfolios (precomputed by src/optimize.py, so the app only reads them)
    summary = load_table("SELECT * FROM portfolio_summary")
    weights = load_table("SELECT portfolio, ticker, weight FROM optimal_weights")
    # The 40 frontier points, ordered by return so the line follows the curve
    frontier = load_table("SELECT ann_vol, ann_return FROM efficient_frontier ORDER BY ann_return")
    # The random portfolios (precomputed by src/optimize.py, table monte_carlo)
    cloud = load_table("SELECT ann_vol, ann_return FROM monte_carlo")
    st.subheader("Portfolio comparison")

    # Tell the reader that the sliders in the sidebar do NOT drive this section
    st.info(
        "The portfolio weights below are precomputed for a fixed set of 35 stocks "
        "(relative screening, score >= 3). They do not change with the sliders in the sidebar."
    )

    # includes rf, max_weight and data_end_date, so the assumptions are visible
    st.dataframe(summary, hide_index=True)

    choice = st.selectbox("Portfolio", summary["portfolio"])   # returns the selected name as a string

    # Keep only the chosen portfolio and the stocks that actually have a position (weight > 0.1%)
    held = weights[(weights["portfolio"] == choice) & (weights["weight"] > 0.001)]
    held = held.sort_values("weight", ascending=False)

    # Two equal-width columns: frontier on the left, weights of the chosen portfolio on the right
    left, right = st.columns(2)

    with left:
        st.markdown("**Efficient frontier**")
        st.plotly_chart(frontier_figure(frontier, summary, cloud))

    with right:
        st.markdown(f"**Weights: {choice}**")
        st.metric("Stocks held", len(held))
        st.plotly_chart(weights_figure(held, PORTFOLIO_COLORS.get(choice, "#4F8EF7")))

        # Exact numbers stay available, out of the way; hide_index removes the database row numbers
        with st.expander("Weights as a table"):
            st.dataframe(held[["ticker", "weight"]].round(4), hide_index=True)