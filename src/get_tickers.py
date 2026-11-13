import pandas as pd
import requests
from io import StringIO
from pathlib import Path

URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def fetch_sp500():
    response = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()

    table = pd.read_html(StringIO(response.text))[0]
    table = table[["Symbol", "Security", "GICS Sector", "GICS Sub-Industry"]]
    table.columns = ["ticker", "name", "sector", "sub_industry"]

    table["ticker"] = table["ticker"].str.replace(".", "-", regex=False)
    return table


if __name__ == "__main__":
    df = fetch_sp500()
    print(f"Βρέθηκαν {df.shape[0]} εταιρείες")
    print(df["sector"].value_counts())

    out_dir = Path("data")
    out_dir.mkdir(exist_ok=True)
    df.to_csv(out_dir / "sp500_universe.csv", index=False)
    print("Αποθηκεύτηκε στο data/sp500_universe.csv")