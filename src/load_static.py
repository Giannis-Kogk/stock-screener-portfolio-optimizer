import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

DB_PATH = Path("data/portfolio.db")
CSV_PATH = Path("data/fundamentals_raw.csv")


def load_static_tables():
    df = pd.read_csv(CSV_PATH)
    df = df.astype(object).where(df.notna(), None)

    fetched_at = datetime.fromtimestamp(CSV_PATH.stat().st_mtime).strftime("%Y-%m-%d %H:%M")

    companies = df[["ticker", "name", "sector", "sub_industry"]].values.tolist()
    fundamentals = df[["ticker", "pe", "forward_pe", "pb", "roe",
                       "peg_ratio", "peg_trailing"]].values.tolist()
    fundamentals = [row + [fetched_at] for row in fundamentals]

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
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
    conn.commit()
    conn.close()
    print(f"Φορτώθηκαν {len(companies)} εταιρείες και {len(fundamentals)} γραμμές θεμελιωδών.")


if __name__ == "__main__":
    load_static_tables()