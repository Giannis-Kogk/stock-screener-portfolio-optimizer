import yfinance as yf

info = yf.Ticker("AAPL").info

fields = ["shortName", "sector", "trailingPE", "forwardPE",
          "priceToBook", "returnOnEquity", "trailingPegRatio", "pegRatio"]

for key in fields:
    print(key, "->", info.get(key))

print([k for k in info if "peg" in k.lower()])