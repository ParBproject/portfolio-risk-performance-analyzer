"""Load cleaned data into SQLite and run the analysis queries in sql/."""

import sqlite3

import pandas as pd

from prpa import config
from prpa.clean import adj_close_panel, load_raw, risk_free_daily

SQL_DIR = config.ROOT / "sql"


def build(db_path=config.DB_PATH) -> None:
    px, _ = adj_close_panel()
    rf = risk_free_daily(px.index)
    con = sqlite3.connect(db_path)
    con.executescript((SQL_DIR / "schema.sql").read_text())
    con.executemany("INSERT INTO assets VALUES (?, ?)", list(config.UNIVERSE.items()))
    rows = []
    for t in config.UNIVERSE:
        raw = load_raw(t).reindex(px.index)
        for d, close, adj, vol in zip(px.index, raw["Close"], px[t], raw["Volume"], strict=True):
            rows.append((d.strftime("%Y-%m-%d"), t, float(close), float(adj), float(vol)))
    con.executemany("INSERT INTO prices VALUES (?, ?, ?, ?, ?)", rows)
    con.executemany(
        "INSERT INTO risk_free VALUES (?, ?)",
        [(d.strftime("%Y-%m-%d"), float(v)) for d, v in rf.items()],
    )
    con.commit()
    con.close()


def query(name: str, db_path=config.DB_PATH) -> pd.DataFrame:
    con = sqlite3.connect(db_path)
    try:
        return pd.read_sql_query((SQL_DIR / f"{name}.sql").read_text(), con)
    finally:
        con.close()


if __name__ == "__main__":
    build()
    for q in ("coverage", "annual_returns", "worst_days"):
        print(f"-- {q}\n{query(q).to_string(index=False)}\n")
