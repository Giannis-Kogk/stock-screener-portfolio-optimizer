import sqlite3
import time
from pathlib import Path

import yfinance as yf

DB_PATH = Path("data/portfolio.db")
PERIOD = "5y"


def fetch_prices(ticker):
    hist = yf.Ticker(ticker).history(period=PERIOD, auto_adjust=True)
    hist = hist.dropna(subset=["Close"])
    dates = hist.index.strftime("%Y-%m-%d")
    return [(ticker, d, float(c)) for d, c in zip(dates, hist["Close"])]


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    tickers = [row[0] for row in conn.execute("SELECT ticker FROM companies ORDER BY ticker")]
    print(f"{len(tickers)} μετοχές προς λήψη")

    failed = []
    for i, ticker in enumerate(tickers, start=1):
        try:
            rows = fetch_prices(ticker)
            if not rows:
                raise ValueError("κενά δεδομένα")
            conn.executemany(
                "INSERT OR REPLACE INTO prices (ticker, date, adj_close) VALUES (?, ?, ?)",
                rows,
            )
            conn.commit()
        except Exception as e:
            failed.append(ticker)
            print(f"Αποτυχία {ticker}: {e}")
        if i % 10 == 0:
            print(f"{i}/{len(tickers)}")
        time.sleep(0.5)

    conn.close()
    print("Αποτυχημένα:", failed)


if __name__ == "__main__":
    main()