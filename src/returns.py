import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

DB_PATH = "data/portfolio.db"

# Name of the price column in the "prices" table.
# I have not seen your exact schema, so verify it with the PRAGMA below
# and change this constant if it differs.
PRICE_COL = "adj_close"

conn = sqlite3.connect(DB_PATH)

# --- Block 1: check the schema before trusting the column name ---
# PRAGMA table_info returns one row per column: (id, name, type, ...)
print(pd.read_sql_query("PRAGMA table_info(prices)", conn)[["name", "type"]])

# --- Block 2: which stocks do we need? ---
# These are the 35 stocks that passed the screening (score >= 3)
tickers = pd.read_sql_query("SELECT ticker FROM screen_results", conn)["ticker"].tolist()
print("Number of tickers:", len(tickers))

# --- Block 3: load prices for those stocks only ---
# One "?" placeholder per ticker; sqlite3 fills them safely from the params list
placeholders = ",".join("?" * len(tickers))
query = f"""
    SELECT ticker, date, {PRICE_COL} AS price
    FROM prices
    WHERE ticker IN ({placeholders})
"""
long_df = pd.read_sql_query(query, conn, params=tickers)
conn.close()

# --- Block 4: reshape from "long" to "wide" ---
# Long: one row per (ticker, date).  Wide: one row per date, one column per ticker.
# Covariance and correlation need the wide shape (a matrix: dates x stocks).
long_df["date"] = pd.to_datetime(long_df["date"])
prices = long_df.pivot(index="date", columns="ticker", values="price").sort_index()

# --- Block 5: daily simple returns ---
# pct_change() = price_today / price_yesterday - 1
# The first row has no previous day, so it becomes NaN and we drop it.
returns = prices.pct_change().dropna()

# --- Block 6: sanity checks (never skip these) ---
print("Prices shape :", prices.shape)
print("Returns shape:", returns.shape)
print("Missing prices:", prices.isna().sum().sum())
print("Date range   :", returns.index.min().date(), "->", returns.index.max().date())
print(returns.iloc[:3, :4])

TRADING_DAYS = 252  # convention: approx. number of trading days in a year

# --- Block 7: annualized return and volatility per stock ---
# Mean return scales linearly with time; std scales with the square root of time
ann_return = returns.mean() * TRADING_DAYS
ann_vol = returns.std() * np.sqrt(TRADING_DAYS)  # pandas std uses ddof=1 (sample std)

summary = pd.DataFrame({"ann_return": ann_return, "ann_vol": ann_vol})
# Return per unit of risk (like Sharpe, but with risk-free rate = 0 for now)
summary["return_per_risk"] = summary["ann_return"] / summary["ann_vol"]
print(summary.sort_values("ann_vol").round(3))

# --- Block 8: correlation matrix (35 x 35) ---
corr = returns.corr()

# Average pairwise correlation: exclude the diagonal (each stock with itself = 1)
off_diagonal = ~np.eye(len(corr), dtype=bool)
print("Average pairwise correlation:", round(corr.values[off_diagonal].mean(), 3))

# --- Block 9: most and least correlated pairs ---
# Keep only the upper triangle (k=1 skips the diagonal) so each pair appears once
upper = np.triu(np.ones(corr.shape, dtype=bool), k=1)

# Keep the upper triangle only, drop the NaNs explicitly (works in every pandas version)
pairs = corr.where(upper).stack().dropna().sort_values()

# Sanity check: 35 stocks -> 35 * 34 / 2 = 595 unique pairs
print("Number of pairs:", len(pairs))

print("Lowest correlation pairs:\n", pairs.head(5).round(3))
print("Highest correlation pairs:\n", pairs.tail(5).round(3))

# --- Block 10: annualized covariance matrix ---
# Covariance (like variance) scales linearly with time, so multiply by 252.
# Result: 35 x 35 matrix; diagonal = variances, off-diagonal = co-movement of pairs.
cov_annual = returns.cov() * TRADING_DAYS

# Sanity check: the square root of the diagonal must equal the annual volatilities
# we computed in Block 7. If this prints False, something is inconsistent.
print("Cov diagonal consistent with ann_vol:",
      np.allclose(np.sqrt(np.diag(cov_annual)), ann_vol.values))

# --- Block 11: a reusable function for portfolio return and risk ---
# weights, mu: 1-D numpy arrays of length n;  cov: n x n numpy array
def portfolio_stats(weights, mu, cov):
    port_return = weights @ mu                 # weighted average of stock returns
    port_vol = np.sqrt(weights @ cov @ weights)  # sqrt of w' * Sigma * w
    return port_return, port_vol

# Convert pandas objects to plain numpy arrays (same stock order in all three!)
mu = ann_return.values
cov = cov_annual.values
n = len(mu)

# --- Block 12: the equal-weight (1/N) portfolio = our benchmark ---
w_equal = np.full(n, 1 / n)                    # each stock gets 1/35 = 2.86%
print("Weights sum to 1:", np.isclose(w_equal.sum(), 1.0))

eq_return, eq_vol = portfolio_stats(w_equal, mu, cov)
print(f"Equal-weight  return: {eq_return:.3f}   vol: {eq_vol:.3f}   "
      f"return/risk: {eq_return / eq_vol:.3f}")

# --- Block 13: how much did diversification help? ---
# If all correlations were 1, portfolio vol would equal the weighted average of the vols
weighted_avg_vol = w_equal @ ann_vol.values
print(f"Weighted average of stock vols: {weighted_avg_vol:.3f}")
print(f"Diversification ratio: {weighted_avg_vol / eq_vol:.2f}")

# --- Block 14: generate random long-only portfolios with a weight cap ---
rng = np.random.default_rng(42)  # fixed seed -> same results on every run
N_TARGET = 20_000   # number of random portfolios we want to keep
CAP = 0.15          # max weight per stock (a judgement, see plan.md)
ALPHA = 0.5         # Dirichlet concentration: <1 -> a few stocks get large weights

kept, drawn = [], 0
while sum(len(b) for b in kept) < N_TARGET:
    # each row: 35 weights, all >= 0, summing to exactly 1
    batch = rng.dirichlet(np.full(n, ALPHA), size=50_000)
    drawn += len(batch)
    # reject any portfolio where some weight exceeds the cap
    kept.append(batch[batch.max(axis=1) <= CAP])

total_kept = sum(len(b) for b in kept)
W = np.vstack(kept)[:N_TARGET]   # matrix: one portfolio per row
print(f"Kept {len(W)} portfolios; acceptance rate ~{total_kept / drawn:.1%}")

# --- Block 15: return and volatility of ALL portfolios at once (no loop) ---
mc_ret = W @ mu                                # (N,) one return per portfolio
# row i of (W @ cov) is w_i' * Sigma; multiplying by W and summing the row gives w_i' Sigma w_i
mc_vol = np.sqrt(((W @ cov) * W).sum(axis=1))  # (N,) one volatility per portfolio
mc_ratio = mc_ret / mc_vol                     # return per unit of risk (risk-free rate = 0 for now)

# Sanity check: the vectorized formula must match our function from Block 11
r0, v0 = portfolio_stats(W[0], mu, cov)
print("Vectorized matches function:", np.isclose(r0, mc_ret[0]) and np.isclose(v0, mc_vol[0]))
print("Max weight in any portfolio:", round(W.max(), 3), "(must be <= 0.15)")

# --- Block 16: the extremes of the random sample ---
tickers_arr = np.array(returns.columns)
i_min = mc_vol.argmin()      # lowest-risk portfolio found
i_best = mc_ratio.argmax()   # best return/risk portfolio found

for label, i in [("Min vol in sample", i_min), ("Best return/risk in sample", i_best)]:
    top = np.argsort(W[i])[::-1][:5]  # indices of the 5 largest weights
    print(f"{label}: return {mc_ret[i]:.3f}, vol {mc_vol[i]:.3f}, ratio {mc_ratio[i]:.3f}")
    print("   top weights:", {tickers_arr[j]: round(W[i][j], 3) for j in top})

print(f"Equal weight : return {eq_return:.3f}, vol {eq_vol:.3f}, ratio {eq_return / eq_vol:.3f}")
print(f"Cloud ranges : vol {mc_vol.min():.3f}-{mc_vol.max():.3f}, "
      f"return {mc_ret.min():.3f}-{mc_ret.max():.3f}")

# --- Block 17: scatter plot of the random portfolios ---
plt.figure(figsize=(8, 5))
sc = plt.scatter(mc_vol, mc_ret, c=mc_ratio, s=4, cmap="viridis")  # colour = return/risk
plt.colorbar(sc, label="return / risk")
plt.scatter(eq_vol, eq_return, c="red", s=70, label="Equal weight")
plt.scatter(mc_vol[i_min], mc_ret[i_min], c="white", edgecolors="black",
            marker="*", s=180, label="Min vol (sample)")
plt.scatter(mc_vol[i_best], mc_ret[i_best], c="orange", edgecolors="black",
            marker="D", s=70, label="Best ratio (sample)")
plt.xlabel("Annualized volatility")
plt.ylabel("Annualized return")
plt.legend()

# Create the output folder if it does not exist yet (exist_ok avoids an error if it does)
Path("images").mkdir(exist_ok=True)

# Save BEFORE plt.show(), otherwise the figure may be empty.
# dpi=150 -> sharp enough for the README; bbox_inches="tight" trims the white margins.
plt.savefig("images/monte_carlo.png", dpi=150, bbox_inches="tight")

plt.show()