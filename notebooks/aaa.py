import sqlite3
conn = sqlite3.connect("data/portfolio.db")
print(conn.execute("SELECT COUNT(*) FROM prices").fetchone())
print(conn.execute(
    "SELECT ticker, COUNT(*) AS n FROM prices GROUP BY ticker HAVING n < 1200 ORDER BY n"
).fetchall())