# Download SPY (S&P 500 ETF) into its own table, separate from the screened stocks.
import sqlite3
from pathlib import Path

import yfinance as yf

# Path built relative to this file, so the script works from any folder
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "portfolio.db"
BENCHMARK = "SPY"   # the benchmark: "buy the whole US market"
PERIOD = "5y"       # same window length as the stock prices


def fetch_benchmark(ticker=BENCHMARK):
    """Daily adjusted closes of the benchmark as a list of (ticker, date, price) tuples."""
    # auto_adjust=True: prices already include splits AND dividends (same choice as for the stocks)
    hist = yf.Ticker(ticker).history(period=PERIOD, auto_adjust=True)
    hist = hist.dropna(subset=["Close"])             # drop days without a price
    dates = hist.index.strftime("%Y-%m-%d")          # keep only the local date, as text
    return [(ticker, d, float(c)) for d, c in zip(dates, hist["Close"])]


def main():
    rows = fetch_benchmark()
    if not rows:
        # yfinance may return an empty table instead of an error, so we raise it ourselves
        raise ValueError("No data returned for the benchmark")

    conn = sqlite3.connect(DB_PATH)
    try:
        # Same shape as `prices`, but WITHOUT a foreign key: SPY is not a row of `companies`
        conn.execute("""
            CREATE TABLE IF NOT EXISTS benchmark_prices (
                ticker    TEXT NOT NULL,
                date      TEXT NOT NULL,
                adj_close REAL NOT NULL,
                PRIMARY KEY (ticker, date)           -- prevents duplicate rows on re-runs
            )
        """)
        # INSERT OR REPLACE: re-running the script updates rows instead of failing
        conn.executemany(
            "INSERT OR REPLACE INTO benchmark_prices (ticker, date, adj_close) VALUES (?, ?, ?)",
            rows,
        )
        conn.commit()

        # Verify what is really in the database, not what we think we wrote
        n, first, last = conn.execute(
            "SELECT COUNT(*), MIN(date), MAX(date) FROM benchmark_prices WHERE ticker = ?",
            (BENCHMARK,),
        ).fetchone()
        print(f"{BENCHMARK}: {n} rows, {first} to {last}")
    finally:
        conn.close()   # always close, even if something above fails


if __name__ == "__main__":
    main()