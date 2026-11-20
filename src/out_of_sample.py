# Out-of-sample test: optimise on period A, evaluate the FIXED weights on A (in-sample) and on B (out-of-sample).
# Run from the repo root: python src/out_of_sample.py
import pandas as pd

from compare_spy import load_spy_returns, spy_stats
from optimize import annual_inputs, load_returns, portfolio_stats
from sensitivity import optimise_period


def main():
    returns = load_returns()
    mid = len(returns) // 2
    train, test = returns.iloc[:mid], returns.iloc[mid:]     # A = first half, B = second half

    weights = optimise_period(train)                         # weights estimated ONLY from A
    weights["equal_weight"] = pd.Series(1 / train.shape[1], index=train.columns)   # 1/N needs no estimation

    spy_all = load_spy_returns()
    for label, data in (("A (in-sample)", train), ("B (out-of-sample)", test)):
        # Same trading days for the stocks and for SPY, otherwise the comparison is not fair
        common = data.index.intersection(spy_all.index)
        mu, cov = annual_inputs(data.loc[common])            # statistics of THIS period

        rows = {name: portfolio_stats(w, mu, cov) for name, w in weights.items()}
        rows["SPY"] = spy_stats(spy_all.loc[common])
        print(f"\n{label}: {len(common)} days | {common.min().date()} to {common.max().date()}")
        print(pd.DataFrame(rows).T.round(3))


if __name__ == "__main__":
    main()