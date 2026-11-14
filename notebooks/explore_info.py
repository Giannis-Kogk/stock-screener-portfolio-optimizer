import yfinance as yf

# One request: the full dict of Yahoo fields for Apple. We use ONE stock as a "sample"
# to see the exact field names before downloading ~109 stocks.
info = yf.Ticker("AAPL").info

# The fields we are interested in (names as Yahoo spells them, not our column names).
fields = ["shortName", "sector", "trailingPE", "forwardPE",
          "priceToBook", "returnOnEquity", "trailingPegRatio", "pegRatio"]

for key in fields:
    # .get() prints None for a missing field instead of raising a KeyError
    print(key, "->", info.get(key))

# Lists every key that contains "peg" (case-insensitive), because we did not know
# which field holds the PEG ratio: yfinance is unofficial and field names can change.
print([k for k in info if "peg" in k.lower()])