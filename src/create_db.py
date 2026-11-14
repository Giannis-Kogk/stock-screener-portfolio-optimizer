import sqlite3
from pathlib import Path

DB_PATH = Path("data/portfolio.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    ticker       TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    sector       TEXT NOT NULL,
    sub_industry TEXT
);

CREATE TABLE IF NOT EXISTS fundamentals (
    ticker       TEXT PRIMARY KEY,
    pe           REAL,
    forward_pe   REAL,
    pb           REAL,
    roe          REAL,
    peg_ratio    REAL,
    peg_trailing REAL,
    fetched_at   TEXT,
    FOREIGN KEY (ticker) REFERENCES companies (ticker)
);

CREATE TABLE IF NOT EXISTS prices (
    ticker    TEXT NOT NULL,
    date      TEXT NOT NULL,
    adj_close REAL NOT NULL,
    PRIMARY KEY (ticker, date),
    FOREIGN KEY (ticker) REFERENCES companies (ticker)
);
"""

def create_database():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    print(f"Η βάση δημιουργήθηκε: {DB_PATH}")
    
if __name__ == "__main__":
    create_database()