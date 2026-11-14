import sqlite3
import time
from pathlib import Path

import yfinance as yf

DB_PATH = Path("data/portfolio.db")
PERIOD = "5y"   # 5 years of daily prices (about 1,255 trading days per stock)


def fetch_prices(ticker):
    # auto_adjust=True: yfinance returns prices already adjusted for splits AND dividends.
    # With this option the "Close" column holds that adjusted price (there is no separate "Adj Close"),
    # and that is the value we store as adj_close. Dividends matter because they are part of the
    # real return, especially for Consumer Staples stocks.
    hist = yf.Ticker(ticker).history(period=PERIOD, auto_adjust=True)
    # Drop days with no price: adj_close is NOT NULL in the prices table, so a None would raise an error.
    hist = hist.dropna(subset=["Close"])
    # The index holds timestamps with a time and a time zone; strftime keeps only the local date as text.
    dates = hist.index.strftime("%Y-%m-%d")
    # One tuple per day: (ticker, date, price), the same order as the columns in the INSERT below.
    # float() turns numpy numbers into plain Python floats, which sqlite3 can store.
    return [(ticker, d, float(c)) for d, c in zip(dates, hist["Close"])]


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")   # reject prices for a ticker that is not in companies
    # The ticker list comes from the database (companies), not from the CSV,
    # so the database is the single source of truth.
    tickers = [row[0] for row in conn.execute("SELECT ticker FROM companies ORDER BY ticker")]
    print(f"{len(tickers)} μετοχές προς λήψη")

    failed = []   # tickers that raised an error or returned no data
    for i, ticker in enumerate(tickers, start=1):
        try:
            rows = fetch_prices(ticker)
            if not rows:
                # yfinance often returns an empty table instead of an error, so we raise it ourselves
                raise ValueError("κενά δεδομένα")
            # executemany inserts all ~1,255 rows of this stock in one call.
            # INSERT OR REPLACE with the key (ticker, date): re-running the script updates rows, no duplicates.
            conn.executemany(
                "INSERT OR REPLACE INTO prices (ticker, date, adj_close) VALUES (?, ?, ?)",
                rows,
            )
            conn.commit()   # commit after every stock: if a later one fails, the earlier ones are already saved
        except Exception as e:
            # One failing stock must not stop the other ones: record it and continue.
            failed.append(ticker)
            print(f"Αποτυχία {ticker}: {e}")
        if i % 10 == 0:
            print(f"{i}/{len(tickers)}")   # progress message every 10 stocks
        time.sleep(0.5)   # short pause between requests to avoid Yahoo rate limits

    conn.close()
    print("Αποτυχημένα:", failed)


if __name__ == "__main__":
    main()