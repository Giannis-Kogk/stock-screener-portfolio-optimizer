import pandas as pd

df = pd.read_csv("data/fundamentals_raw.csv")
print(df[df["pe"].isna()][["ticker", "name", "sector", "forward_pe", "roe"]])