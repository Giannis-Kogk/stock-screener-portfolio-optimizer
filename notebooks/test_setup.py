import sqlite3
import yfinance as yf

# 1. Θεμελιώδεις δείκτες μιας εταιρείας
ticker = yf.Ticker("AAPL")
info = ticker.info
print("Εταιρεία:", info.get("shortName"))
print("P/E:", info.get("trailingPE"))
print("ROE:", info.get("returnOnEquity"))
print("P/BV:", info.get("priceToBook"))

# 2. Ιστορικές τιμές
prices = ticker.history(period="1mo")
print(prices[["Close"]].tail())

# 3. SQLite
print("SQLite:", sqlite3.sqlite_version)