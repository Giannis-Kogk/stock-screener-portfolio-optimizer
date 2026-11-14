import sqlite3
import pandas as pd

# Connect to the SQLite database created on Day 3
conn = sqlite3.connect("data/portfolio.db")

# Load one row per company: sector from `companies`, ratios from `fundamentals`.
# Columns are named explicitly so that `ticker` appears only once
# (SELECT f.* would bring a duplicate `ticker` column).
df = pd.read_sql_query(
    "SELECT c.ticker, c.sector, f.pe, f.forward_pe, f.pb, f.roe, "
    "f.peg_ratio, f.peg_trailing "
    "FROM companies c JOIN fundamentals f ON c.ticker = f.ticker",
    conn,
)
conn.close()  # the data is now in memory (df), so the connection is no longer needed

# ---------------------------------------------------------------
# STEP 1: Where are the missing values?
# ---------------------------------------------------------------
print(df.columns.tolist())
print()
# isna() marks every NULL/NaN as True; sum() counts the True values per column.
# Expected: pe 5, roe 7, peg_ratio 1, peg_trailing 12.
print(df.isna().sum())
print()

# Columns known to contain gaps (the ones we want to inspect in this step)
gap_cols = ["pe", "roe", "peg_trailing", "peg_ratio"]

# axis=1 means "per row": keep stocks with at least one missing value
# among the columns in `gap_cols`.
missing = df[df[gap_cols].isna().any(axis=1)]
print(missing[["ticker", "sector"] + gap_cols].to_string(index=False))

# ---------------------------------------------------------------
# STEP 2: Why is ROE missing? (hypothesis: negative book equity)
# ---------------------------------------------------------------
# Stocks with missing ROE; a negative P/B next to them would suggest
# negative equity, where ROE has no meaningful value.
roe_na = df[df["roe"].isna()]
print(roe_na[["ticker", "pe", "pb", "forward_pe"]].to_string(index=False))

# Check ALL stocks with negative P/B, not only those with missing ROE.
# Some (CLX, IT) have a defined but meaningless ROE (534%, 366%).
neg_pb = df[df["pb"] < 0]
print(neg_pb[["ticker", "pb", "roe"]].to_string(index=False))
print(len(neg_pb), "μετοχές με αρνητικό P/BV")

# Compare as sets (order ignored): False means the two groups differ,
# i.e. negative equity is not the same thing as "ROE is missing".
same = set(neg_pb["ticker"]) == set(roe_na["ticker"])
print("Ίδιο σύνολο με τα κενά ROE:", same)

# ---------------------------------------------------------------
# STEP 3: Rule flags (True = the rule excludes the stock)
# ---------------------------------------------------------------
# Rule 1: negative book equity -> P/B and ROE cannot be interpreted
df["flag_negative_equity"] = df["pb"] < 0
# Rule 2: missing P/E -> no positive earnings, so "cheap by P/E" cannot be judged
df["flag_no_positive_earnings"] = df["pe"].isna()

# Count how many stocks trigger each rule (expected: 9 and 5)
print(df[["flag_negative_equity", "flag_no_positive_earnings"]].sum())
# `&` means "and": how many stocks trigger BOTH rules (expected: 0)
print("Επικάλυψη:", (df["flag_negative_equity"] & df["flag_no_positive_earnings"]).sum())

# ---------------------------------------------------------------
# STEP 4: Extreme values among the stocks that pass both rules
# ---------------------------------------------------------------
# `|` means "or"; `~` negates: keep stocks that triggered NO rule.
bad = df["flag_negative_equity"] | df["flag_no_positive_earnings"]
# .copy() makes an independent DataFrame, so adding columns later is safe
clean = df[~bad].copy()
print("Μετοχές για screening:", len(clean))

# Ratios whose distribution we inspect for outliers
ratio_cols = ["pe", "forward_pe", "pb", "roe", "peg_ratio"]
# describe(): count, mean, std, min, quartiles, max.
# A large gap between mean and the median (50%) signals outliers.
print(clean[ratio_cols].describe().round(2))

# The 3 lowest and 3 highest values per ratio, with their tickers
for c in ratio_cols:
    print(c, "χαμηλότερες:", clean.nsmallest(3, c)[["ticker", c]].round(2).values.tolist())
    print(c, "υψηλότερες: ", clean.nlargest(3, c)[["ticker", c]].round(2).values.tolist())

# ---------------------------------------------------------------
# STEP 5: Short price history
# ---------------------------------------------------------------
MIN_DAYS = 756  # minimum trading days of history (~3 years); a judgement call

# New connection: the previous one was closed after loading `df`
conn = sqlite3.connect("data/portfolio.db")
# For each ticker: number of price rows and the date of the first row
counts = pd.read_sql_query(
    "SELECT ticker, COUNT(*) AS n_days, MIN(date) AS first_date "
    "FROM prices GROUP BY ticker",
    conn,
)
conn.close()

# The 5 stocks with the shortest history (expected: VYLR, Q, SNDK first)
print(counts.sort_values("n_days").head(5).to_string(index=False))

# how="left" keeps all 109 rows of df and adds n_days / first_date to each
df = df.merge(counts, on="ticker", how="left")
# Rule 3: fewer trading days than required
df["flag_short_history"] = df["n_days"] < MIN_DAYS

# any(axis=1): True if at least one of the three rules fired for the stock
flags = ["flag_negative_equity", "flag_no_positive_earnings", "flag_short_history"]
df["excluded"] = df[flags].any(axis=1)

print(df[flags].sum())                          # per-rule counts: 9, 5, 3
print("Αποκλείονται συνολικά:", df["excluded"].sum())   # expected: 17
print("Μένουν:", (~df["excluded"]).sum())               # expected: 92