import sqlite3          # built into Python; no pip install needed (that is why it is not in requirements.txt)
import yfinance as yf   # unofficial Yahoo Finance wrapper; source of both fundamentals and prices

# 1. Θεμελιώδεις δείκτες μιας εταιρείας
ticker = yf.Ticker("AAPL")   # creates an object for one company; no data is downloaded yet
info = ticker.info           # first network request: a dict with hundreds of fields (P/E, ROE, ...)

# .get() returns None when a key is missing, while info["key"] would raise a KeyError.
# This matters later: across ~100 stocks some indicators will always be missing.
print("Εταιρεία:", info.get("shortName"))
print("P/E:", info.get("trailingPE"))        # price / earnings of the last 12 months
print("ROE:", info.get("returnOnEquity"))    # a decimal, not a percentage (1.5 means 150%)
print("P/BV:", info.get("priceToBook"))      # price / book value per share

# 2. Ιστορικές τιμές
prices = ticker.history(period="1mo")   # second request: a pandas DataFrame, one row per trading day
print(prices[["Close"]].tail())         # keep only the Close column, show the last 5 rows

# 3. SQLite
# Sanity check that the sqlite3 module works; prints the version of the SQLite engine, not of the database.
print("SQLite:", sqlite3.sqlite_version)