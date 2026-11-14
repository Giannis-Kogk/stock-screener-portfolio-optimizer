import yfinance as yf

hist = yf.Ticker("NVDA").history(period="5y", auto_adjust=True)

raw = yf.Ticker("NVDA").history(period="5y", auto_adjust=False)
print(raw.loc["2024-06-05":"2024-06-12", ["Close", "Adj Close"]])

print(hist.head())
print(hist.shape)
print(hist.index[:3])
print(hist["Close"].isna().sum())