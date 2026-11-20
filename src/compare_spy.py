# Compare the three portfolios with SPY over their common trading days.
# Run from the repo root: python src/compare_spy.py
import sqlite3

import numpy as np
import pandas as pd

# optimize.py lives in the same folder as this file, so a plain import works when running this script
from optimize import DB_PATH, RISK_FREE, TRADING_DAYS, annual_inputs, load_returns, portfolio_stats


def load_spy_returns(db_path=DB_PATH):
    """Daily simple returns of SPY, indexed by date."""
    conn = sqlite3.connect(db_path)
    try:
        prices = pd.read_sql(
            "SELECT date, adj_close FROM benchmark_prices WHERE ticker = 'SPY' ORDER BY date",
            conn, parse_dates=["date"], index_col="date",
        )["adj_close"]
    finally:
        conn.close()
    return prices.pct_change().dropna()    # the first row is NaN by construction


def load_weights(db_path=DB_PATH):
    """Stored optimal weights as a dict: portfolio name -> Series of weights indexed by ticker."""
    conn = sqlite3.connect(db_path)
    try:
        long = pd.read_sql("SELECT portfolio, ticker, weight FROM optimal_weights", conn)
    finally:
        conn.close()
    # One Series per portfolio; the ticker label (not the position) is what links weights to mu and cov
    return {name: g.set_index("ticker")["weight"] for name, g in long.groupby("portfolio")}


def spy_stats(spy_ret, rf=RISK_FREE):
    """Same formulas as portfolio_stats, so the numbers are directly comparable."""
    ret = float(spy_ret.mean() * TRADING_DAYS)              # annualised mean daily return
    vol = float(spy_ret.std() * np.sqrt(TRADING_DAYS))      # annualised volatility
    return {"ann_return": ret, "ann_vol": vol, "sharpe": (ret - rf) / vol}


def main():
    stock_ret = load_returns()
    spy_ret = load_spy_returns()

    # Keep only the days present in BOTH series, so both sides are measured over the same period
    common = stock_ret.index.intersection(spy_ret.index)
    stock_ret, spy_ret = stock_ret.loc[common], spy_ret.loc[common]
    print(f"Common days: {len(common)} | {common.min().date()} to {common.max().date()}")

    mu, cov = annual_inputs(stock_ret)      # recomputed on the common window
    weights = load_weights()

    rows = {name: portfolio_stats(w, mu, cov) for name, w in weights.items()}
    rows["SPY"] = spy_stats(spy_ret)
    table = pd.DataFrame(rows).T            # one row per portfolio, one column per statistic
    print(table.round(3))


if __name__ == "__main__":
    main()