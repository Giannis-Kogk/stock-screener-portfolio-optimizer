import sqlite3
conn = sqlite3.connect("data/portfolio.db")
# sqlite_master is SQLite's built-in catalogue of everything stored in the database.
# Filtering with type='table' lists only the tables; expected result: companies, fundamentals, prices
# (data_quality is also expected now, since clean_data.py created it on Day 4).
print(conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())