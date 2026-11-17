# Day 7: Markowitz optimisation (block 1: data loading)
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from scipy.optimize import minimize
import matplotlib.pyplot as plt

# Path to the database, built relative to this file so it works from any folder
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "portfolio.db"

TRADING_DAYS = 252   # used to annualise daily statistics
MAX_WEIGHT = 0.15    # per-stock cap (a judgement call, see plan.md)
RISK_FREE = 0.04   # annual risk-free rate (judgement: Fed range 3.75-4%, 3M T-bill ~3.95%)

# --- Load adjusted close prices of the 35 screened stocks (long format) ---
conn = sqlite3.connect(DB_PATH)
query = """
SELECT p.ticker, p.date, p.adj_close
FROM prices AS p
JOIN screen_results AS s ON s.ticker = p.ticker
"""
prices_long = pd.read_sql(query, conn, parse_dates=["date"])
conn.close()

# Wide format: one row per date, one column per ticker
prices = prices_long.pivot(index="date", columns="ticker", values="adj_close")

# Daily simple returns; the first row is NaN by construction, so we drop it
returns = prices.pct_change().dropna()

tickers = list(returns.columns)   # fixes the order of the weight vector
n = len(tickers)                  # number of assets (35)

# --- Annualised inputs of the optimiser ---
mu = returns.mean().values * TRADING_DAYS        # expected annual returns, shape (n,)
cov = returns.cov().values * TRADING_DAYS        # annual covariance matrix, shape (n, n)

# --- Sanity check: must reproduce the equal-weight result of Day 6 ---
w_eq = np.full(n, 1 / n)                         # 1/N weights
eq_return = w_eq @ mu                            # portfolio return = w . mu
eq_vol = np.sqrt(w_eq @ cov @ w_eq)              # portfolio volatility = sqrt(w' Sigma w)
print(f"prices {prices.shape}, returns {returns.shape}, NaN: {int(returns.isna().sum().sum())}")
print(f"Equal weight: return {eq_return:.1%}, vol {eq_vol:.1%}, ratio {eq_return / eq_vol:.3f}")


# --- Block 2: minimum variance portfolio (long-only, per-stock cap) ---

def portfolio_variance(w, cov):
    # Objective function: w' * Sigma * w (the quantity SLSQP will minimise)
    return w @ cov @ w

w0 = np.full(n, 1 / n)                      # starting point: equal weights (feasible)
bounds = [(0.0, MAX_WEIGHT)] * n            # 0 <= w_i <= 15% for every stock
constraints = (
    # 'eq' means fun(w) must equal 0 -> weights sum to exactly 1 (fully invested)
    {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
)

res_minvar = minimize(
    portfolio_variance,
    w0,
    args=(cov,),                            # extra argument passed to the objective
    method="SLSQP",
    bounds=bounds,
    constraints=constraints,
    options={"maxiter": 1000, "ftol": 1e-12},   # ftol: stopping tolerance
)

w_minvar = res_minvar.x                     # optimal weight vector
mv_return = w_minvar @ mu
mv_vol = np.sqrt(w_minvar @ cov @ w_minvar)

print("Converged:", res_minvar.success, "|", res_minvar.message)
print(f"Sum of weights: {w_minvar.sum():.6f}, max weight: {w_minvar.max():.4f}")
print(f"Min variance: return {mv_return:.2%}, vol {mv_vol:.1%}")
print(f"Stocks with weight > 0.1%: {(w_minvar > 0.001).sum()}, at the cap: {(w_minvar > MAX_WEIGHT - 1e-6).sum()}")

weights_minvar = pd.Series(w_minvar, index=tickers).sort_values(ascending=False)
print(weights_minvar.head(10).round(4))

# --- Block 3: maximum Sharpe portfolio (same bounds and constraints as block 2) ---

def neg_sharpe(w, mu, cov, rf):
    # Objective: minus the Sharpe ratio, because minimize() can only minimise
    port_ret = w @ mu                       # expected annual portfolio return
    port_vol = np.sqrt(w @ cov @ w)         # annual portfolio volatility
    return -(port_ret - rf) / port_vol      # excess return per unit of risk (negated)

res_sharpe = minimize(
    neg_sharpe,
    w0,                                     # start: equal weights
    args=(mu, cov, RISK_FREE),
    method="SLSQP",
    bounds=bounds,                          # 0 <= w_i <= MAX_WEIGHT
    constraints=constraints,                # sum of weights = 1
    options={"maxiter": 1000, "ftol": 1e-12},
)
w_sharpe = res_sharpe.x

def summarize(name, w):
    # Return, volatility and Sharpe ratio of a weight vector, as one table row
    r = w @ mu
    v = np.sqrt(w @ cov @ w)
    return {"portfolio": name, "return": r, "vol": v, "sharpe": (r - RISK_FREE) / v,
            "n_stocks": int((w > 0.001).sum()), "at_cap": int((w >= MAX_WEIGHT - 1e-6).sum())}

print("Converged:", res_sharpe.success, "|", res_sharpe.message)
table = pd.DataFrame([
    summarize("equal weight (1/N)", w_eq),
    summarize("min variance", w_minvar),
    summarize("max Sharpe", w_sharpe),
]).set_index("portfolio")
print(table.round(3))

weights_sharpe = pd.Series(w_sharpe, index=tickers).sort_values(ascending=False)
print(weights_sharpe.head(10).round(4))


# --- Block 4: efficient frontier (min variance for a grid of target returns) ---

def min_vol_for_target(target, w_start):
    # Minimise variance subject to: weights sum to 1 AND portfolio return == target
    cons = (
        {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
        {"type": "eq", "fun": lambda w: w @ mu - target},   # 'target' is fixed per call
    )
    return minimize(portfolio_variance, w_start, args=(cov,), method="SLSQP",
                    bounds=bounds, constraints=cons, options={"maxiter": 1000, "ftol": 1e-12})

# Highest return reachable under the same bounds: minimise the negative return (linear problem)
res_maxret = minimize(lambda w: -(w @ mu), w0, method="SLSQP",
                      bounds=bounds, constraints=constraints)
max_ret = res_maxret.x @ mu
print(f"Return range of the frontier: {mv_return:.2%} (min variance) to {max_ret:.2%} (max return)")

# Grid of targets; the last point is shifted slightly because at the extreme only one portfolio is feasible
targets = np.linspace(mv_return, max_ret - 1e-4, 40)

frontier = []
w_prev = w_minvar                                  # warm start: previous solution is a good guess
for t in targets:
    res = min_vol_for_target(t, w_prev)
    if res.success:
        frontier.append((t, np.sqrt(res.fun)))     # res.fun is the variance -> take the square root
        w_prev = res.x
frontier = np.array(frontier)                      # columns: return, volatility
print(f"Frontier points solved: {len(frontier)} of {len(targets)}")

# Validation: max Sharpe must lie ON the frontier (same return -> same minimum volatility)
chk = min_vol_for_target(w_sharpe @ mu, w_sharpe)
print(f"Max Sharpe vol {np.sqrt(w_sharpe @ cov @ w_sharpe):.4f} vs frontier vol at the same return {np.sqrt(chk.fun):.4f}")

# --- Plot and save to a file (needed for the README) ---
stock_vol = np.sqrt(np.diag(cov))                  # volatility of each single stock
fig, ax = plt.subplots(figsize=(9, 6))
ax.scatter(stock_vol, mu, s=15, alpha=0.5, label="individual stocks")
ax.plot(frontier[:, 1], frontier[:, 0], lw=2, label=f"efficient frontier (cap {MAX_WEIGHT:.0%})")
for name, w in {"1/N": w_eq, "min variance": w_minvar, "max Sharpe": w_sharpe}.items():
    ax.scatter(np.sqrt(w @ cov @ w), w @ mu, s=120, marker="*", zorder=3, label=name)
ax.set_xlabel("Annual volatility")
ax.set_ylabel("Annual return")
ax.legend()
ax.grid(alpha=0.3)

fig_dir = Path(__file__).resolve().parent.parent / "figures"
fig_dir.mkdir(exist_ok=True)                       # create the folder if it does not exist
fig.savefig(fig_dir / "efficient_frontier.png", dpi=150, bbox_inches="tight")
plt.show()
