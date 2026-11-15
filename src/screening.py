import sqlite3
import pandas as pd

conn = sqlite3.connect("data/portfolio.db")

# Base query: one row per non-excluded company (identity + ratios)
query = """
SELECT c.ticker, c.name, c.sector,
       f.pe, f.pb, f.roe, f.peg_ratio
FROM companies AS c
JOIN fundamentals AS f ON f.ticker = c.ticker      -- match rows by ticker
JOIN data_quality AS q ON q.ticker = c.ticker      -- add the cleaning flags
WHERE q.excluded = 0                               -- drop the 17 flagged stocks
"""
df = pd.read_sql_query(query, conn)

# Sanity checks from Step 2: 92 rows, no NaN, ratio scales
print(df.shape)
print(df["sector"].value_counts())
print(df.isna().sum())
print(df[["pe", "pb", "roe", "peg_ratio"]].describe())

# ---- Step 3: screening ----
# Thresholds are judgment calls, not laws (we test their sensitivity later)
MAX_PE = 25      # price / earnings: pay at most 25x yearly earnings
MAX_PB = 3       # price / book value: pay at most 3x the accounting equity
MIN_ROE = 0.15   # return on equity, stored as a fraction (0.15 = 15%)
MAX_PEG = 1.5    # P/E relative to expected growth (lower = cheaper for its growth)

# How many of the 92 stocks pass each criterion ON ITS OWN?
# (df["pe"] <= MAX_PE) is a True/False column; .sum() counts the True values
print("pass P/E  :", (df["pe"] <= MAX_PE).sum())
print("pass P/B  :", (df["pb"] <= MAX_PB).sum())
print("pass ROE  :", (df["roe"] >= MIN_ROE).sum())
print("pass PEG  :", (df["peg_ratio"] <= MAX_PEG).sum())

# The same filters in SQL: extend the base query with AND conditions.
# The "?" placeholders are filled from `params` in the same order.
screen_query = query + """
  AND f.pe <= ?
  AND f.pb <= ?
  AND f.roe >= ?
  AND f.peg_ratio <= ?
ORDER BY f.pe
"""
passed = pd.read_sql_query(
    screen_query, conn, params=(MAX_PE, MAX_PB, MIN_ROE, MAX_PEG)
)
print("pass ALL four:", len(passed))
print(passed)

# True where a stock FAILS a criterion (the opposite of the pass conditions)
fail = pd.DataFrame({
    "P/E": df["pe"] > MAX_PE,
    "P/B": df["pb"] > MAX_PB,
    "ROE": df["roe"] < MIN_ROE,
    "PEG": df["peg_ratio"] > MAX_PEG,
})

# For each row, keep the names of the failed criteria and join them in one text
# row.index[row] selects the column names where the value is True
df["reasons"] = fail.apply(lambda row: ", ".join(row.index[row]), axis=1)

rejected = df[df["reasons"] != ""]      # empty text = passed everything
print("rejected:", len(rejected))       # expected: 92 - 3 = 89
print(rejected[["ticker", "sector", "reasons"]].head(15))

print(fail.sum())                       # stocks failing each criterion
print(fail.groupby(df["sector"]).sum()) # the same, split by sector

ratios = ["pe", "pb", "roe", "peg_ratio"]

# Median per sector: the middle value, robust to outliers such as CRWD (P/E 4535)
sector_median = df.groupby("sector")[ratios].median()
# Mean per sector, only to measure how much the outliers distort it
sector_mean = df.groupby("sector")[ratios].mean()

print("MEDIAN per sector")
print(sector_median.round(2))
print("MEAN per sector")
print(sector_mean.round(2))

# Each row receives the median of ITS OWN sector.
# transform() keeps one row per stock, unlike agg()/median() which gives one row per sector
med = df.groupby("sector")[ratios].transform("median")

# True where the stock is better than its sector median
rel = pd.DataFrame({
    "P/E": df["pe"] <= med["pe"],
    "P/B": df["pb"] <= med["pb"],
    "ROE": df["roe"] >= med["roe"],
    "PEG": df["peg_ratio"] <= med["peg_ratio"],
})
df["score"] = rel.sum(axis=1)          # number of criteria passed, from 0 to 4

print(df["score"].value_counts().sort_index())
print(df.groupby("sector")["score"].value_counts().unstack(fill_value=0))
print(df[df["score"] == 4][["ticker", "sector", "pe", "pb", "roe", "peg_ratio"]])

# Candidate universe for the optimizer: stocks that beat their sector median
# on at least 3 of the 4 criteria (a design choice, to be documented in Limitations)
selected = df[df["score"] >= 3][
    ["ticker", "name", "sector", "pe", "pb", "roe", "peg_ratio", "score"]
]

# if_exists="replace" drops and rebuilds the table on every run (same idea as data_quality)
selected.to_sql("screen_results", conn, if_exists="replace", index=False)
conn.commit()    # make sure the write is saved

# Verify from the database itself, not from the DataFrame
print(pd.read_sql_query(
    "SELECT sector, COUNT(*) AS n FROM screen_results GROUP BY sector", conn
))

conn.close()   # keep this as the last line of the file