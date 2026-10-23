"""Load cleaned data into SQLite and run the analysis queries in sql/."""

import math
import sqlite3

import pandas as pd

from prpa import config
from prpa.clean import adj_close_panel, load_raw, risk_free_daily

SQL_DIR = config.ROOT / "sql"


QUERIES = [
    "coverage",
    "annual_returns",
    "worst_days",
    "annual_summary",
    "monthly_hit_rate",
    "rolling_vol_summary",
    "drawdown_episodes",
    "stress_periods",
    "correlation_by_regime",
    "stock_bond_corr_by_year",
]


def connect(db_path=config.DB_PATH) -> sqlite3.Connection:
    """Open SQLite, registering ln/exp/sqrt if this SQLite build lacks math functions."""
    con = sqlite3.connect(db_path)
    try:
        con.execute("SELECT ln(1), exp(0), sqrt(1)")
    except sqlite3.OperationalError:
        con.create_function("ln", 1, math.log, deterministic=True)
        con.create_function("exp", 1, math.exp, deterministic=True)
        con.create_function("sqrt", 1, math.sqrt, deterministic=True)
    return con


def build(db_path=config.DB_PATH) -> None:
    from prpa.analysis import run

    px, _ = adj_close_panel()
    rf = risk_free_daily(px.index)
    con = connect(db_path)
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
    r = run()
    strat = [(d.strftime("%Y-%m-%d"), "EQUAL_WEIGHT", float(v)) for d, v in r["port"].items()]
    con.executemany("INSERT INTO strategy_returns VALUES (?, ?, ?)", strat)
    con.executescript((SQL_DIR / "views.sql").read_text())
    con.commit()
    con.close()


def query(name: str, db_path=config.DB_PATH) -> pd.DataFrame:
    con = connect(db_path)
    try:
        return pd.read_sql_query((SQL_DIR / f"{name}.sql").read_text(), con)
    finally:
        con.close()


if __name__ == "__main__":
    build()
    for q in QUERIES:
        print(f"-- {q}\n{query(q).to_string(index=False)}\n")
