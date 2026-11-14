import sqlite3
import pandas as pd

DB_PATH = "data/portfolio.db"
MIN_DAYS = 756  # minimum trading days of price history required (~3 years)

conn = sqlite3.connect(DB_PATH)

# One row per company with the two ratios the rules need
df = pd.read_sql_query(
    "SELECT c.ticker, f.pe, f.pb "
    "FROM companies c JOIN fundamentals f ON c.ticker = f.ticker",
    conn,
)

# Number of price rows (trading days) available for each ticker
counts = pd.read_sql_query(
    "SELECT ticker, COUNT(*) AS n_days FROM prices GROUP BY ticker",
    conn,
)
df = df.merge(counts, on="ticker", how="left")

# A ticker with no prices at all would get NaN here, and NaN < 756 evaluates
# to False, so it would silently pass the history rule. Treat it as 0 days.
df["n_days"] = df["n_days"].fillna(0)


# Rule flags: 1 = rule triggered, 0 = not triggered (SQLite has no boolean type)
df["negative_equity"] = (df["pb"] < 0).astype(int)        # P/B < 0 -> book equity is negative
df["no_positive_earnings"] = df["pe"].isna().astype(int)  # missing P/E -> no positive earnings
df["short_history"] = (df["n_days"] < MIN_DAYS).astype(int)

rules = ["negative_equity", "no_positive_earnings", "short_history"]

# A stock is excluded if at least one rule fired (max of 0/1 flags = logical OR)
df["excluded"] = df[rules].max(axis=1)

# Human-readable reason, e.g. "negative_equity" or "negative_equity,short_history"
df["reason"] = df[rules].apply(
    lambda row: ",".join(name for name in rules if row[name] == 1), axis=1
)
df.loc[df["reason"] == "", "reason"] = None  # kept stocks get NULL, not an empty string


# The table is derived from the rules, so rebuild it from scratch on every run
conn.execute("DROP TABLE IF EXISTS data_quality")
conn.execute(
    """
    CREATE TABLE data_quality (
        ticker               TEXT PRIMARY KEY,
        negative_equity      INTEGER NOT NULL,
        no_positive_earnings INTEGER NOT NULL,
        short_history        INTEGER NOT NULL,
        excluded             INTEGER NOT NULL,
        reason               TEXT,
        FOREIGN KEY (ticker) REFERENCES companies(ticker)
    )
    """
)

cols = ["ticker"] + rules + ["excluded", "reason"]
conn.executemany(
    "INSERT INTO data_quality VALUES (?, ?, ?, ?, ?, ?)",
    df[cols].itertuples(index=False, name=None),  # plain tuples, one per row
)
conn.commit()

# Verification: read back from the database, not from the DataFrame
print(pd.read_sql_query(
    "SELECT excluded, COUNT(*) AS n FROM data_quality GROUP BY excluded", conn
))
print(pd.read_sql_query(
    "SELECT ticker, reason FROM data_quality WHERE excluded = 1 ORDER BY reason, ticker",
    conn,
).to_string(index=False))
conn.close()