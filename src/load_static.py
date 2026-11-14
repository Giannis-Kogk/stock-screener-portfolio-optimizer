import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

DB_PATH = Path("data/portfolio.db")           # database created by create_db.py
CSV_PATH = Path("data/fundamentals_raw.csv")  # raw table saved by fetch_fundamentals.py


def load_static_tables():
    df = pd.read_csv(CSV_PATH)
    # Convert the whole table to plain Python objects and replace every NaN (empty cell) with None.
    # sqlite3 stores None as NULL, so a missing P/E or ROE stays "empty" and is never turned into 0.
    df = df.astype(object).where(df.notna(), None)

    # Download time = last modification time of the CSV, formatted as text.
    # It is an approximation: it is only correct while the CSV has not been modified or copied since the download.
    fetched_at = datetime.fromtimestamp(CSV_PATH.stat().st_mtime).strftime("%Y-%m-%d %H:%M")

    # Split the one wide CSV into the columns that belong to each table.
    # .values.tolist() gives a list of rows, each row a list, in the same column order as the SQL below.
    companies = df[["ticker", "name", "sector", "sub_industry"]].values.tolist()
    fundamentals = df[["ticker", "pe", "forward_pe", "pb", "roe",
                       "peg_ratio", "peg_trailing"]].values.tolist()
    # Append the same download time to every fundamentals row (it fills the fetched_at column).
    fundamentals = [row + [fetched_at] for row in fundamentals]

    conn = sqlite3.connect(DB_PATH)
    # SQLite checks FOREIGN KEY only if this is switched on, and only for this connection.
    # With it on, a fundamentals row whose ticker is not in companies is rejected.
    conn.execute("PRAGMA foreign_keys = ON")
    # companies must be loaded BEFORE fundamentals, because fundamentals refers to it (foreign key).
    # INSERT OR REPLACE: if a row with the same primary key exists it is replaced, so the script
    # can be re-run without errors or duplicates. A plain INSERT would fail on the second run.
    # The ? marks are placeholders filled from the lists (safer than building the SQL text by hand).
    conn.executemany(
        "INSERT OR REPLACE INTO companies (ticker, name, sector, sub_industry) "
        "VALUES (?, ?, ?, ?)",
        companies,
    )
    conn.executemany(
        "INSERT OR REPLACE INTO fundamentals "
        "(ticker, pe, forward_pe, pb, roe, peg_ratio, peg_trailing, fetched_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        fundamentals,
    )
    conn.commit()   # nothing is saved permanently until commit
    conn.close()
    print(f"Φορτώθηκαν {len(companies)} εταιρείες και {len(fundamentals)} γραμμές θεμελιωδών.")


if __name__ == "__main__":
    load_static_tables()