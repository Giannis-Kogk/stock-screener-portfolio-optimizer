import pandas as pd
import requests
from io import StringIO      # wraps a string so pandas can read it as if it were a file
from pathlib import Path     # object-style file paths, used below to create the data folder

# Wikipedia page that holds the S&P 500 constituents table (%26 is the URL encoding of "&")
URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def fetch_sp500():
    # Wikipedia often rejects requests without a browser-like User-Agent, so we send one.
    # timeout=30 stops the program from hanging forever if the site does not answer.
    response = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    # Stops with a clear error (e.g. 403) instead of silently parsing an error page.
    response.raise_for_status()

    # read_html returns a list with one DataFrame per HTML table on the page;
    # the companies table is the first one ([0]).
    table = pd.read_html(StringIO(response.text))[0]
    # Keep only the 4 columns we need, then give them short names
    # that will later become column names in the SQLite database.
    table = table[["Symbol", "Security", "GICS Sector", "GICS Sub-Industry"]]
    table.columns = ["ticker", "name", "sector", "sub_industry"]

    # Wikipedia writes BRK.B, while yfinance expects BRK-B.
    # Without this fix such tickers would fail silently in later downloads.
    # regex=False means "." is treated as a plain dot, not as "any character".
    table["ticker"] = table["ticker"].str.replace(".", "-", regex=False)
    return table


# Runs only when the file is executed directly (python src/get_tickers.py),
# not when another script imports fetch_sp500 from it.
if __name__ == "__main__":
    df = fetch_sp500()
    print(f"Βρέθηκαν {df.shape[0]} εταιρείες")   # shape[0] = number of rows = number of companies
    print(df["sector"].value_counts())            # companies per sector, used to pick the 2 sectors

    # Save the table so later steps read the file instead of re-downloading from Wikipedia.
    # The path "data" is relative: run the script from the project root,
    # otherwise the folder is created in the wrong place.
    out_dir = Path("data")
    out_dir.mkdir(exist_ok=True)   # exist_ok=True: no error if the folder already exists
    df.to_csv(out_dir / "sp500_universe.csv", index=False)   # index=False: skip the 0,1,2... row-number column
    print("Αποθηκεύτηκε στο data/sp500_universe.csv")