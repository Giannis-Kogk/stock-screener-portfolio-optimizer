# Stability check: optimise on two halves of the data and compare the weights.
# Run from the repo root: python src/sensitivity.py
import pandas as pd

from optimize import annual_inputs, load_returns, max_sharpe_weights, min_variance_weights


def optimise_period(returns):
    """Min variance and max Sharpe weights (Series by ticker) estimated on one period only."""
    mu, cov = annual_inputs(returns)            # mean returns and covariance of THIS period
    return {
        "min_variance": min_variance_weights(cov),
        "max_sharpe": max_sharpe_weights(mu, cov),
    }


def compare(kind, w_a, w_b):
    """Print how much the weights of period A and period B differ."""
    # Share of the portfolio that would have to change: 0 = identical, 1 = no stock in common
    shift = 0.5 * (w_a - w_b).abs().sum()
    # A stock counts as 'held' above 0.1% (the optimiser leaves tiny non-zero residuals)
    held_a, held_b = set(w_a[w_a > 0.001].index), set(w_b[w_b > 0.001].index)
    print(f"\n{kind}: shift {shift:.2f} | held A {len(held_a)}, held B {len(held_b)}, "
          f"in both {len(held_a & held_b)}")

    table = pd.DataFrame({"A": w_a, "B": w_b})
    table = table[(table > 0.001).any(axis=1)]       # keep stocks held in at least one period
    print(table.sort_values("A", ascending=False).round(3))


def main():
    returns = load_returns()                         # all 1,254 daily returns of the 35 stocks
    mid = len(returns) // 2                          # split by number of days: two equal halves
    periods = {"A": returns.iloc[:mid], "B": returns.iloc[mid:]}

    results = {}
    for name, r in periods.items():
        print(f"Period {name}: {len(r)} days | {r.index.min().date()} to {r.index.max().date()}")
        results[name] = optimise_period(r)

    for kind in ("min_variance", "max_sharpe"):
        compare(kind, results["A"][kind], results["B"][kind])


if __name__ == "__main__":
    main()