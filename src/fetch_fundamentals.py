import yfinance as yf
import time
import pandas as pd

# Maps the field name used by yfinance -> the column name we use in our own data.
# To add or rename an indicator, we only change this one place.
FIELDS = {
    "trailingPE": "pe",                 # price / earnings of the last 12 months
    "forwardPE": "forward_pe",          # price / expected (analyst) earnings
    "priceToBook": "pb",                # price / book value per share
    "returnOnEquity": "roe",            # a decimal: 1.42 means 142%
    "trailingPegRatio": "peg_trailing", # two different PEG fields: we download both
    "pegRatio": "peg_ratio",            # and decide later which one is more complete
}
UNIVERSE_PATH = "data/sp500_universe.csv"     # input: the S&P 500 table saved by get_tickers.py
OUTPUT_PATH = "data/fundamentals_raw.csv"     # output: raw indicators, before any cleaning
SECTORS = ["Information Technology", "Consumer Staples"]   # the two sectors we study (GICS names)


def fetch_fundamentals(ticker):
    # One network request per ticker: returns a dict with hundreds of Yahoo fields.
    info = yf.Ticker(ticker).info
    row = {"ticker": ticker}
    for yf_key, column in FIELDS.items():
        # .get() returns None when Yahoo has no value, so a missing field
        # does not crash the program; it becomes an empty cell later.
        row[column] = info.get(yf_key)
    return row


def main():
    universe = pd.read_csv(UNIVERSE_PATH)
    # Keep only the rows whose sector is in our list (isin = "is one of these").
    selected = universe[universe["sector"].isin(SECTORS)]
    print(f"Επιλέχθηκαν {len(selected)} μετοχές")

    # rows: successful results; failed: tickers that raised an error
    rows, failed = [], []
    for i, ticker in enumerate(selected["ticker"], start=1):   # i counts from 1, used for progress output
        try:
            rows.append(fetch_fundamentals(ticker))
        except Exception as e:
            # One bad stock must not stop the other ~108: record it and continue.
            # "except Exception" is deliberately broad here (simple educational script).
            failed.append(ticker)
            print(f"Αποτυχία {ticker}: {e}")
        if i % 10 == 0:
            print(f"{i}/{len(selected)}")   # progress message every 10 stocks
        time.sleep(0.5)   # short pause between requests so Yahoo does not rate-limit us

    fundamentals = pd.DataFrame(rows)   # list of dicts -> table, one row per stock
    # Join the sp500_universe columns (name, sector, sub_industry) with the indicators using ticker as key.
    # how="left" keeps every selected stock, even if its indicators are missing.
    # The sector comes from our CSV (GICS), not from yfinance, because Yahoo uses different sector names.
    result = selected.merge(fundamentals, on="ticker", how="left")
    result.to_csv(OUTPUT_PATH, index=False)

    # Count of empty cells per column: this is the real quality check,
    # because yfinance often returns empty data for a bad ticker instead of raising an error.
    print(result.isna().sum())
    print("Αποτυχημένα:", failed)


if __name__ == "__main__":
    main()