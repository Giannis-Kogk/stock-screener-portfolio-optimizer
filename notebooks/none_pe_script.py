import pandas as pd

# Reads the raw table saved by src/fetch_fundamentals.py
df = pd.read_csv("data/fundamentals_raw.csv")

# df["pe"].isna() is True for each row with an empty P/E; using it as a filter keeps only those rows.
# Then we show only the columns that help explain the gap:
# forward_pe and roe tell us whether the company seems to have no positive earnings.
print(df[df["pe"].isna()][["ticker", "name", "sector", "forward_pe", "roe"]])