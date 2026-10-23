"""Data validation: the frozen snapshot is intact and clean."""

import json
import sqlite3

import pandas as pd
import pytest

from prpa import config
from prpa.clean import adj_close_panel, load_raw, risk_free_daily, validate_prices
from prpa.ingest import verify


def test_manifest_hashes_match():
    verify()


def test_manifest_covers_universe():
    files = json.loads(config.MANIFEST.read_text())["files"]
    assert {m["ticker"] for m in files.values()} == set(config.UNIVERSE) | {config.RISK_FREE}


def test_panel_clean():
    px, log = adj_close_panel()
    assert list(px.columns) == list(config.UNIVERSE)
    assert log["rows_clean"] == len(px) > 5000
    validate_prices(px)


def test_adj_close_not_above_close_for_dividend_payers():
    # dividends reduce historical adjusted prices relative to raw; first row must satisfy it
    for t in ("SPY", "AGG", "VNQ"):
        raw = load_raw(t)
        assert raw["Adj Close"].iloc[0] < raw["Close"].iloc[0]


def test_no_absurd_daily_moves():
    px, _ = adj_close_panel()
    assert px.pct_change().abs().max().max() < 0.25


def test_risk_free_reasonable():
    px, _ = adj_close_panel()
    rf = risk_free_daily(px.index) * config.TRADING_DAYS
    assert rf.notna().all() and rf.min() > -0.01 and rf.max() < 0.07


@pytest.mark.parametrize("bad", ["dup", "neg", "nan", "unsorted"])
def test_validate_rejects(bad):
    idx = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"])
    df = pd.DataFrame({"A": [1.0, 2.0, 3.0]}, index=idx)
    if bad == "dup":
        df.index = pd.to_datetime(["2020-01-01", "2020-01-01", "2020-01-03"])
    elif bad == "neg":
        df.iloc[1, 0] = -1
    elif bad == "nan":
        df.iloc[1, 0] = float("nan")
    else:
        df = df.iloc[::-1]
    with pytest.raises(ValueError):
        validate_prices(df)


def test_sqlite_matches_panel(tmp_path):
    from prpa.db import build

    db = tmp_path / "t.sqlite"
    build(db)
    con = sqlite3.connect(db)
    n = con.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
    spy = con.execute(
        "SELECT adj_close FROM prices WHERE ticker='SPY' ORDER BY date DESC LIMIT 1"
    ).fetchone()[0]
    con.close()
    px, _ = adj_close_panel()
    assert n == px.size
    assert spy == pytest.approx(px["SPY"].iloc[-1])


def test_results_pinned():
    """README numbers come from results/stage1.json; recomputing must reproduce them."""
    from prpa.analysis import run
    from prpa.metrics import summary

    saved = json.loads(config.RESULTS.read_text())
    r = run()
    got = summary(r["port"], r["rf"])
    for k in ("annualized_return", "annualized_vol", "sharpe", "max_drawdown"):
        assert got[k] == pytest.approx(saved["equal_weight"][k], abs=1e-10)
