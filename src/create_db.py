import sqlite3
from pathlib import Path

DB_PATH = Path("data/portfolio.db")   # the whole database is one file; SQLite creates it on first connect

# The schema = the "blueprint" of the 3 tables, written in SQL inside one text block.
SCHEMA = """
-- One row per company: static information, stored once instead of repeating it in every price row.
CREATE TABLE IF NOT EXISTS companies (
    ticker       TEXT PRIMARY KEY,   -- unique identifier; also the key that links the 3 tables
    name         TEXT NOT NULL,      -- NOT NULL: a company without a name is invalid data
    sector       TEXT NOT NULL,
    sub_industry TEXT                -- may be empty
);

-- One row per company: valuation indicators. Empty values are allowed (stored as NULL, never as 0),
-- because a missing P/E means "no positive earnings", while 0 would look like a very cheap stock.
CREATE TABLE IF NOT EXISTS fundamentals (
    ticker       TEXT PRIMARY KEY,
    pe           REAL,
    forward_pe   REAL,
    pb           REAL,
    roe          REAL,               -- a decimal: 1.42 means 142%
    peg_ratio    REAL,
    peg_trailing REAL,
    fetched_at   TEXT,               -- date of download; the yfinance data is live and changes between runs
    FOREIGN KEY (ticker) REFERENCES companies (ticker)   -- every ticker here must exist in companies
);

-- One row per company per trading day: the large table (about 134k rows).
CREATE TABLE IF NOT EXISTS prices (
    ticker    TEXT NOT NULL,
    date      TEXT NOT NULL,         -- stored as text in YYYY-MM-DD, which sorts correctly
    adj_close REAL NOT NULL,         -- adjusted close price; a price row without a price is meaningless
    PRIMARY KEY (ticker, date),      -- composite key: a ticker alone repeats on every date, the pair is unique
    FOREIGN KEY (ticker) REFERENCES companies (ticker)
);
"""

def create_database():
    DB_PATH.parent.mkdir(exist_ok=True)     # create the data/ folder if it does not exist
    conn = sqlite3.connect(DB_PATH)         # opens the file, or creates it if it is missing
    conn.executescript(SCHEMA)              # runs several SQL statements in one call
    conn.commit()                           # saves the changes permanently
    conn.close()                            # always release the connection
    print(f"Η βάση δημιουργήθηκε: {DB_PATH}")
    
if __name__ == "__main__":
    create_database()