import yfinance as yf

# Prices adjusted for splits AND dividends (this is what we store in the database).
hist = yf.Ticker("NVDA").history(period="5y", auto_adjust=True)

# Unadjusted download, with both columns "Close" and "Adj Close" side by side.
# Used to compare them around 10 June 2024, when NVIDIA did a 10-for-1 stock split.
raw = yf.Ticker("NVDA").history(period="5y", auto_adjust=False)
# Label-based slice by date: only 5-12 June 2024, only the two price columns.
print(raw.loc["2024-06-05":"2024-06-12", ["Close", "Adj Close"]])

print(hist.head())           # first 5 rows: a quick look at the table layout
print(hist.shape)            # (rows, columns): expected 1255 trading days
print(hist.index[:3])        # first 3 index values: the index has a time and a time zone,
                             # which is why fetch_data.py uses strftime("%Y-%m-%d")
print(hist["Close"].isna().sum())   # number of empty Close values: 0 means no cleaning needed for NVDA