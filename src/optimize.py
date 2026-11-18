# Markowitz optimisation of the screened stocks. Importing this file runs nothing.
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from scipy.optimize import minimize

# Paths are built relative to this file, so the script works from any folder
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "portfolio.db"

# Default parameters (judgement calls, see plan.md); the functions below receive them as arguments
TRADING_DAYS = 252   # used to annualise daily statistics
MAX_WEIGHT = 0.15    # per-stock cap
RISK_FREE = 0.04     # annual risk-free rate (judgement: Fed range 3.75-4%, 3M T-bill ~3.95%)

# Random-portfolio cloud for the chart (judgement calls, same logic as src/returns.py)
N_CLOUD = 10_000     # how many random portfolios are stored in the database
CLOUD_ALPHA = 0.5    # Dirichlet concentration: < 1 -> a few stocks get large weights
CLOUD_SEED = 42      # fixed seed -> the same cloud on every run


def load_returns(db_path=DB_PATH):
    """Daily simple returns of the screened stocks: one row per date, one column per ticker."""
    query = """
    SELECT p.ticker, p.date, p.adj_close
    FROM prices AS p
    JOIN screen_results AS s ON s.ticker = p.ticker
    """
    conn = sqlite3.connect(db_path)
    try:
        prices_long = pd.read_sql(query, conn, parse_dates=["date"])
    finally:
        conn.close()  # always close, even if the query fails

    # Wide format: one column per ticker
    prices = prices_long.pivot(index="date", columns="ticker", values="adj_close")
    # The first row of pct_change() is NaN by construction, so dropna() removes it
    return prices.pct_change().dropna()


def annual_inputs(returns):
    """Annualised mean returns (Series by ticker) and covariance matrix (DataFrame, tickers x tickers)."""
    mu = returns.mean() * TRADING_DAYS
    cov = returns.cov() * TRADING_DAYS
    return mu, cov


def portfolio_stats(w, mu, cov, rf=RISK_FREE):
    """Annual return, volatility and Sharpe ratio of a weight Series.

    pandas aligns w, mu and cov by ticker label, so the order of the weights cannot be mixed up silently.
    """
    ret = float(w @ mu)                    # sum of weight_i * mean return_i
    vol = float(np.sqrt(w @ cov @ w))      # sqrt(w' Sigma w)
    return {"ann_return": ret, "ann_vol": vol, "sharpe": (ret - rf) / vol}

def _optimise(objective, args, n, max_weight, extra_constraints=(), w_start=None):
    """Minimise `objective` over n weights with 0 <= w_i <= max_weight and sum(w) = 1.

    extra_constraints: additional SLSQP constraints (the frontier uses a target return).
    w_start: starting point; the default is the equal-weight portfolio.
    Raises RuntimeError if the optimiser does not converge.
    """
    w0 = np.full(n, 1 / n) if w_start is None else w_start   # default start: equal weights (always feasible)
    bounds = [(0.0, max_weight)] * n             # 0 <= w_i <= max_weight for every stock
    constraints = (
        {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},   # 'eq': must equal 0 -> weights sum to 1
        *extra_constraints,                                   # e.g. a target return (used for the frontier)
    )
    res = minimize(objective, w0, args=args, method="SLSQP", bounds=bounds,
                   constraints=constraints, options={"maxiter": 1000, "ftol": 1e-12})
    if not res.success:
        # Fail loudly: silently continuing with unconverged weights would corrupt every later result
        raise RuntimeError(f"Optimiser did not converge: {res.message}")
    return res


def _variance(w, cov):
    # Objective for min variance: w' Sigma w
    return w @ cov @ w


def _neg_sharpe(w, mu, cov, rf):
    # Objective for max Sharpe. minimize() can only minimise, so we return the NEGATIVE Sharpe ratio
    return -(w @ mu - rf) / np.sqrt(w @ cov @ w)


def min_variance_weights(cov, max_weight=MAX_WEIGHT):
    """Weights (Series by ticker) of the long-only minimum variance portfolio."""
    res = _optimise(_variance, (cov.values,), len(cov), max_weight)
    # SLSQP may return -1e-12 instead of 0; clip back into the allowed range
    return pd.Series(np.clip(res.x, 0.0, max_weight), index=cov.columns)


def max_sharpe_weights(mu, cov, rf=RISK_FREE, max_weight=MAX_WEIGHT):
    """Weights (Series by ticker) of the long-only maximum Sharpe portfolio."""
    res = _optimise(_neg_sharpe, (mu.values, cov.values, rf), len(mu), max_weight)
    return pd.Series(np.clip(res.x, 0.0, max_weight), index=mu.index)

def efficient_frontier(mu, cov, max_weight=MAX_WEIGHT, n_points=40):
    """DataFrame with the volatility of the minimum variance portfolio for each target return."""
    n = len(mu)
    mu_v, cov_v = mu.values, cov.values              # SLSQP works with plain arrays

    w_mv = min_variance_weights(cov, max_weight)
    low = float(w_mv @ mu)                           # lowest return on the frontier
    # Highest feasible return under the same bounds: minimise the NEGATIVE return, then flip the sign
    high = -_optimise(lambda w: -(w @ mu_v), (), n, max_weight).fun
    # The last target is shifted slightly: at the very extreme only one portfolio is feasible
    targets = np.linspace(low, high - 1e-4, n_points)

    rows, w_prev = [], w_mv.values                   # warm start: the previous solution is a good guess
    for target in targets:
        # t=target freezes the CURRENT target inside this constraint function
        hit_target = {"type": "eq", "fun": lambda w, t=target: w @ mu_v - t}
        res = _optimise(_variance, (cov_v,), n, max_weight, (hit_target,), w_start=w_prev)
        rows.append((float(np.sqrt(res.fun)), float(target)))   # res.fun is the variance -> take sqrt
        w_prev = res.x
    return pd.DataFrame(rows, columns=["ann_vol", "ann_return"])


def monte_carlo_cloud(mu, cov, max_weight=MAX_WEIGHT, n_target=N_CLOUD,
                      alpha=CLOUD_ALPHA, seed=CLOUD_SEED):
    """Random long-only portfolios with a per-stock cap: DataFrame with ann_vol and ann_return.

    Same recipe as src/returns.py: Dirichlet weights (>= 0, sum 1), then reject any
    portfolio in which some weight exceeds max_weight.
    """
    # mu and cov must list the tickers in the same order, otherwise W @ mu and W @ cov @ W would mismatch
    if not (mu.index == cov.index).all() or not (mu.index == cov.columns).all():
        raise ValueError("mu and cov are not aligned on the same tickers")

    n = len(mu)
    rng = np.random.default_rng(seed)                # fixed seed -> reproducible cloud
    kept, total = [], 0
    while total < n_target:
        # each row: n weights, all >= 0, summing to exactly 1
        batch = rng.dirichlet(np.full(n, alpha), size=50_000)
        batch = batch[batch.max(axis=1) <= max_weight]   # keep only portfolios that respect the cap
        kept.append(batch)
        total += len(batch)
    W = np.vstack(kept)[:n_target]                   # matrix: one portfolio per row

    ret = W @ mu.values                              # (N,) one return per portfolio
    # row i of (W @ cov) is w_i' Sigma; times W and summed over the row gives w_i' Sigma w_i
    vol = np.sqrt(((W @ cov.values) * W).sum(axis=1))
    return pd.DataFrame({"ann_vol": vol, "ann_return": ret})


def save_results(weights, mu, cov, frontier, cloud, data_end_date, rf=RISK_FREE,
                 max_weight=MAX_WEIGHT, db_path=DB_PATH):
    """Write the results to SQLite. Each table is rebuilt on every run (if_exists='replace')."""
    # dict of Series -> one long table; the dict keys and the tickers become the two index levels
    weights_long = pd.concat(weights, names=["portfolio", "ticker"]).rename("weight").reset_index()

    # One row per portfolio, plus the parameters the numbers depend on
    summary = pd.DataFrame(
        [{"portfolio": name, **portfolio_stats(w, mu, cov, rf)} for name, w in weights.items()]
    )
    summary["rf"] = rf                          # risk-free rate used in the Sharpe ratio
    summary["max_weight"] = max_weight          # per-stock cap used in the optimisation
    summary["data_end_date"] = data_end_date    # last trading day in the data, as 'YYYY-MM-DD' text

    conn = sqlite3.connect(db_path)
    try:
        weights_long.to_sql("optimal_weights", conn, if_exists="replace", index=False)
        summary.to_sql("portfolio_summary", conn, if_exists="replace", index=False)
        frontier.to_sql("efficient_frontier", conn, if_exists="replace", index=False)
        cloud.to_sql("monte_carlo", conn, if_exists="replace", index=False)   # random portfolios for the chart
    finally:
        conn.close()


def main():
    returns = load_returns()
    mu, cov = annual_inputs(returns)

    # Compute everything first, write afterwards: a failed optimisation never leaves half-written tables
    weights = {
        "equal_weight": pd.Series(1 / len(mu), index=mu.index),   # 1/N benchmark
        "min_variance": min_variance_weights(cov),
        "max_sharpe": max_sharpe_weights(mu, cov),
    }
    frontier = efficient_frontier(mu, cov)
    cloud = monte_carlo_cloud(mu, cov)

    for name, w in weights.items():
        s = portfolio_stats(w, mu, cov)
        print(f"{name:13s} return {s['ann_return']:.3f} | vol {s['ann_vol']:.3f} | "
              f"Sharpe {s['sharpe']:.3f} | sum {w.sum():.6f} | min {w.min():.1e}")

    # Sanity check: no random portfolio may lie ABOVE the frontier (the frontier is the best return per risk).
    # np.interp reads the frontier's return at each cloud volatility (the frontier is sorted by volatility).
    frontier_ret = np.interp(cloud["ann_vol"], frontier["ann_vol"], frontier["ann_return"])
    n_above = int((cloud["ann_return"] > frontier_ret + 1e-3).sum())   # 1e-3 tolerates the straight-line interpolation
    print(f"Cloud: {len(cloud)} portfolios | vol {cloud['ann_vol'].min():.3f}-{cloud['ann_vol'].max():.3f} | "
          f"return {cloud['ann_return'].min():.3f}-{cloud['ann_return'].max():.3f} | above frontier: {n_above}")

    save_results(weights, mu, cov, frontier, cloud, returns.index.max().strftime("%Y-%m-%d"))
    print("Saved: optimal_weights, portfolio_summary, efficient_frontier, monte_carlo")



if __name__ == "__main__":
    main()