import yfinance as yf
import time
import pandas as pd

FIELDS = {
    "trailingPE": "pe",
    "forwardPE": "forward_pe",
    "priceToBook": "pb",
    "returnOnEquity": "roe",
    "trailingPegRatio": "peg_trailing",
    "pegRatio": "peg_ratio",
}
UNIVERSE_PATH = "data/sp500_universe.csv"
OUTPUT_PATH = "data/fundamentals_raw.csv"
SECTORS = ["Information Technology", "Consumer Staples"]


def fetch_fundamentals(ticker):
    info = yf.Ticker(ticker).info
    row = {"ticker": ticker}
    for yf_key, column in FIELDS.items():
        row[column] = info.get(yf_key)
    return row


def main():
    universe = pd.read_csv(UNIVERSE_PATH)
    selected = universe[universe["sector"].isin(SECTORS)]
    print(f"Επιλέχθηκαν {len(selected)} μετοχές")

    rows, failed = [], []
    for i, ticker in enumerate(selected["ticker"], start=1):
        try:
            rows.append(fetch_fundamentals(ticker))
        except Exception as e:
            failed.append(ticker)
            print(f"Αποτυχία {ticker}: {e}")
        if i % 10 == 0:
            print(f"{i}/{len(selected)}")
        time.sleep(0.5)

    fundamentals = pd.DataFrame(rows)
    result = selected.merge(fundamentals, on="ticker", how="left")
    result.to_csv(OUTPUT_PATH, index=False)

    print(result.isna().sum())
    print("Αποτυχημένα:", failed)


if __name__ == "__main__":
    main()