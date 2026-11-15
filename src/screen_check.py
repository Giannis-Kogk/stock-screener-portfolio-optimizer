import sqlite3

# Open the database created on Day 3 (path is relative to the project root)
conn = sqlite3.connect("data/portfolio.db")
cur = conn.cursor()

# Part A: how SQLite treats NULL in comparisons
# NULL > 0.15 and NULL = NULL are "unknown", which Python shows as None.
# Only "IS NULL" can actually test for a missing value (returns 1 = true).
cur.execute("SELECT NULL > 0.15, NULL = NULL, NULL IS NULL")
print("NULL test:", cur.fetchone())

# Part A (extra): NULL is not the same as 0
# NULL = 0 is "unknown" (None); 0 IS NULL is false (0) because 0 is a known value
cur.execute("SELECT NULL = 0, 0 IS NULL")
print("NULL vs 0:", cur.fetchone())   # expected: (None, 0)

# Part B: list the column names of each table, so that the JOIN
# in the next step uses names that really exist
for table in ("companies", "fundamentals", "data_quality"):
    cur.execute(f"PRAGMA table_info({table})")   # one row per column
    col_names = [row[1] for row in cur.fetchall()]   # index 1 = column name
    print(table, "->", col_names)

conn.close()