"""Corrupted inputs, manifest and schema checks, edge cases, end-to-end rebuild."""

import json
import shutil
import sqlite3
import sys
import types

import numpy as np
import pandas as pd
import pytest

from prpa import clean, config, ingest, metrics
from prpa.optimize import min_variance
from prpa.portfolio import backtest, backtest_weights


@pytest.fixture
def raw_copy(tmp_path, monkeypatch):
    """A private copy of the frozen snapshot that tests may corrupt."""
    raw = tmp_path / "raw"
    shutil.copytree(config.RAW_DIR, raw)
    man = tmp_path / "manifest.json"
    shutil.copy(config.MANIFEST, man)
    monkeypatch.setattr(config, "RAW_DIR", raw)
    monkeypatch.setattr(config, "MANIFEST", man)
    return raw, man


# ---------- corrupted input ----------
def test_verify_fails_on_one_changed_byte(raw_copy):
    raw, _ = raw_copy
    p = raw / "TLT.csv"
    b = bytearray(p.read_bytes())
    i = b.rindex(b"5")
    b[i] = ord("6")  # change one digit of one price
    p.write_bytes(bytes(b))
    with pytest.raises(ValueError, match="TLT.csv: hash mismatch"):
        ingest.verify()


def test_verify_fails_on_missing_file(raw_copy):
    raw, _ = raw_copy
    (raw / "GLD.csv").unlink()
    with pytest.raises(FileNotFoundError):
        ingest.verify()


def test_negative_price_rejected(raw_copy):
    raw, _ = raw_copy
    df = pd.read_csv(raw / "AGG.csv", index_col="date")
    df.iloc[100, df.columns.get_loc("Adj Close")] = -1.0
    df.to_csv(raw / "AGG.csv")
    with pytest.raises(ValueError, match="non-positive"):
        clean.adj_close_panel()


def test_duplicate_date_rejected(raw_copy):
    raw, _ = raw_copy
    df = pd.read_csv(raw / "SPY.csv", index_col="date")
    pd.concat([df, df.iloc[[50]]]).sort_index().to_csv(raw / "SPY.csv")
    with pytest.raises(ValueError):
        clean.adj_close_panel()


def test_short_gap_ffilled_long_gap_dropped(raw_copy):
    raw, _ = raw_copy
    df = pd.read_csv(raw / "GLD.csv", index_col="date")
    short = df.index[200:202]  # 2 missing days -> forward-filled
    long_ = df.index[400:405]  # 5 missing days -> 3 filled, last 2 rows dropped
    df.drop(index=list(short) + list(long_)).to_csv(raw / "GLD.csv")
    px, log = clean.adj_close_panel()
    assert log["missing_before"] == 7
    assert log["missing_after_ffill"] == 2
    assert log["rows_clean"] == log["rows_raw"] - 2
    assert px.loc[short[0], "GLD"] == px["GLD"].iloc[199]


# ---------- manifest ----------
def test_manifest_fields_match_files():
    m = json.loads(config.MANIFEST.read_text())
    assert {"source", "adjustment", "downloaded_utc", "start", "end_exclusive", "files"} <= set(m)
    for name, meta in m["files"].items():
        df = pd.read_csv(config.RAW_DIR / name, index_col="date", parse_dates=True)
        assert len(df) == meta["rows"]
        assert str(df.index[0].date()) == meta["first"]
        assert str(df.index[-1].date()) == meta["last"]
        assert len(meta["sha256"]) == 64 and int(meta["sha256"], 16) >= 0
        assert list(df.columns) == ["Open", "High", "Low", "Close", "Adj Close", "Volume"]


def test_no_unlisted_raw_files():
    m = json.loads(config.MANIFEST.read_text())
    assert {p.name for p in config.RAW_DIR.glob("*.csv")} == set(m["files"])


def test_ingest_download_with_fake_yfinance(tmp_path, monkeypatch):
    """The download path writes CSVs + a manifest that verify() accepts (no network)."""
    idx = pd.bdate_range("2020-01-01", periods=5, name="Date")
    cols = pd.MultiIndex.from_product(
        [["Open", "High", "Low", "Close", "Adj Close", "Volume"], ["X"]]
    )
    fake = types.SimpleNamespace(
        __version__="fake",
        download=lambda *a, **k: pd.DataFrame(np.arange(30.0).reshape(5, 6) + 1, idx, cols),
    )
    monkeypatch.setitem(sys.modules, "yfinance", fake)
    monkeypatch.setattr(config, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(config, "MANIFEST", tmp_path / "m.json")
    ingest.download()
    ingest.verify()
    m = json.loads((tmp_path / "m.json").read_text())
    assert m["source"].endswith("fake") and m["files"]["SPY.csv"]["rows"] == 5


# ---------- schema ----------
@pytest.fixture(scope="module")
def db(tmp_path_factory):
    from prpa.db import build, connect

    p = tmp_path_factory.mktemp("s") / "t.sqlite"
    build(p)
    con = connect(p)
    yield con
    con.close()


def test_schema_objects(db):
    objs = dict(db.execute("SELECT name, type FROM sqlite_master").fetchall())
    for t in ("assets", "prices", "risk_free", "strategy_returns", "stress_periods"):
        assert objs[t] == "table"
    for v in ("v_returns", "v_monthly", "v_annual", "v_drawdown"):
        assert objs[v] == "view"
    cols = [r[1] for r in db.execute("PRAGMA table_info(prices)")]
    assert cols == ["date", "ticker", "close", "adj_close", "volume"]


def test_schema_rejects_bad_rows(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO prices VALUES ('2030-01-01','SPY',-1,1,0)")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO prices SELECT * FROM prices LIMIT 1")  # duplicate PK
    db.rollback()


def test_no_nulls_and_counts(db):
    assert db.execute("SELECT COUNT(*) FROM prices WHERE adj_close IS NULL").fetchone()[0] == 0
    n = db.execute("SELECT COUNT(DISTINCT date) FROM prices").fetchone()[0]
    assert db.execute("SELECT COUNT(*) FROM risk_free").fetchone()[0] == n
    assert db.execute("SELECT COUNT(*) FROM strategy_returns").fetchone()[0] == n - 1


def test_connect_registers_math_fallback(monkeypatch, tmp_path):
    from prpa import db as dbmod

    class Con:
        def __init__(self):
            self.funcs = {}

        def execute(self, sql):
            raise sqlite3.OperationalError("no such function: ln")

        def create_function(self, name, n, f, deterministic):
            self.funcs[name] = f

    fake = Con()
    monkeypatch.setattr(dbmod.sqlite3, "connect", lambda p: fake)
    dbmod.connect(tmp_path / "x")
    assert set(fake.funcs) == {"ln", "exp", "sqrt"} and fake.funcs["exp"](0) == 1


# ---------- calculation edge cases ----------
def s(vals):
    return pd.Series(vals, index=pd.bdate_range("2020-01-01", periods=len(vals)), dtype=float)


def test_zero_vol_sharpe_is_not_finite():
    assert not np.isfinite(metrics.sharpe(s([0.001] * 10)))


def test_all_losses_drawdown_is_compounded():
    assert metrics.max_drawdown(s([-0.5, -0.5])) == pytest.approx(-0.75)


def test_total_loss_floor():
    assert metrics.total_return(s([-1.0, 0.5])) == -1.0
    assert metrics.max_drawdown(s([-1.0])) == -1.0


def test_sharpe_with_series_rf_aligned():
    r = s([0.01, 0.02, 0.0, 0.01])
    rf = pd.Series(0.001, index=r.index)
    assert metrics.sharpe(r, rf) == pytest.approx(metrics.sharpe(r, 0.001))


def test_min_variance_single_asset_and_singular():
    assert min_variance(np.array([[0.04]])).tolist() == [1.0]
    # two identical assets: covariance is singular on the full support; still valid
    w = min_variance(np.array([[0.04, 0.04], [0.04, 0.04]]))
    assert w.sum() == pytest.approx(1.0) and (w >= 0).all()


def test_min_variance_ignores_ordering():
    cov = np.array([[0.04, 0.006, 0.0], [0.006, 0.01, 0.002], [0.0, 0.002, 0.09]])
    perm = [2, 0, 1]
    w = min_variance(cov)
    wp = min_variance(cov[np.ix_(perm, perm)])
    np.testing.assert_allclose(wp, w[perm], atol=1e-12)


def test_backtest_missing_column_weights_error():
    idx = pd.bdate_range("2021-01-27", periods=2)
    rets = pd.DataFrame(0.0, index=idx, columns=["A", "B"])
    with pytest.raises(ValueError):
        backtest(rets, pd.Series({"A": 1.0}))  # B gets NaN weight -> sum != 1


def test_equal_targets_match_both_backtests():
    """backtest (fixed target) and backtest_weights (dated targets) agree."""
    idx = pd.bdate_range("2021-01-25", periods=30)
    rng = np.random.default_rng(1)
    rets = pd.DataFrame(rng.normal(0, 0.01, (30, 2)), index=idx, columns=["A", "B"])
    from prpa.portfolio import rebalance_dates

    rd = rebalance_dates(idx)
    wts = pd.DataFrame(0.5, index=[idx[0]] + list(rd), columns=["A", "B"])
    a, _ = backtest(rets.iloc[1:], pd.Series({"A": 0.5, "B": 0.5}))
    b, _ = backtest_weights(rets, wts)
    pd.testing.assert_series_equal(a, b)


# ---------- end-to-end regeneration ----------
def test_result_scripts_reproduce_committed_files(tmp_path, monkeypatch, capsys):
    from prpa import analysis, stage3, stage4

    monkeypatch.setattr(config, "RESULTS", tmp_path / "s1.json")
    monkeypatch.setattr(stage3, "OUT", tmp_path / "s3.json")
    monkeypatch.setattr(stage4, "OUT", tmp_path / "s4.json")
    monkeypatch.setattr(stage4, "WEIGHTS_CSV", tmp_path / "w.csv")
    analysis.main()
    stage3.main()
    stage4.main()
    capsys.readouterr()
    root = config.ROOT / "results"
    for fresh, committed in (
        ("s1.json", "stage1.json"),
        ("s3.json", "stage3.json"),
        ("s4.json", "stage4.json"),
    ):
        _assert_json_close(
            json.loads((tmp_path / fresh).read_text()), json.loads((root / committed).read_text())
        )
    _assert_json_close(_csv_cells(tmp_path / "w.csv"), _csv_cells(root / "stage4_weights.csv"))


def test_query_runner_writes_every_query(tmp_path, monkeypatch, capsys):
    sys.path.insert(0, str(config.ROOT / "scripts"))
    import run_queries

    from prpa import db as dbmod

    monkeypatch.setattr(run_queries, "OUT", tmp_path)
    monkeypatch.setattr(dbmod.config, "DB_PATH", tmp_path / "x.sqlite")
    monkeypatch.setattr(run_queries, "build", lambda: dbmod.build(tmp_path / "x.sqlite"))
    monkeypatch.setattr(run_queries, "query", lambda q: dbmod.query(q, tmp_path / "x.sqlite"))
    run_queries.main()
    capsys.readouterr()
    for q in dbmod.QUERIES:
        got = pd.read_csv(tmp_path / f"{q}.csv")
        ref = pd.read_csv(config.ROOT / "results" / "sql" / f"{q}.csv")
        pd.testing.assert_frame_equal(got, ref)


def test_sortino_no_downside_is_nan():
    assert np.isnan(metrics.sortino(s([0.01, 0.02, 0.03])))


def _assert_json_close(a, b, path="$", rtol=1e-12, atol=1e-12):
    """Recursive compare: floats within rtol/atol; strings, ints, bools, keys, structure exact."""
    if isinstance(a, float) or isinstance(b, float):
        assert isinstance(a, (int, float)) and isinstance(b, (int, float)), path
        assert not isinstance(a, bool) and not isinstance(b, bool), path
        assert abs(a - b) <= atol + rtol * abs(b), f"{path}: {a!r} != {b!r}"
    elif isinstance(a, dict):
        assert isinstance(b, dict) and list(a) == list(b), f"{path}: keys differ"
        for k in a:
            _assert_json_close(a[k], b[k], f"{path}.{k}", rtol, atol)
    elif isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b), f"{path}: length differs"
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            _assert_json_close(x, y, f"{path}[{i}]", rtol, atol)
    else:
        assert type(a) is type(b) and a == b, f"{path}: {a!r} != {b!r}"


def _csv_cells(p):
    """Parse CSV; cells that look like floats become floats, ints stay ints, else strings."""

    def conv(c):
        try:
            return int(c)
        except ValueError:
            try:
                return float(c)
            except ValueError:
                return c

    return [[conv(c) for c in line.split(",")] for line in p.read_text().splitlines()]
