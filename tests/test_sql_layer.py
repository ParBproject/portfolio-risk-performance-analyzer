"""The SQL analysis layer must agree with independent pandas calculations."""

import numpy as np
import pandas as pd
import pytest

from prpa import metrics
from prpa.analysis import run
from prpa.db import build, connect


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    db = tmp_path_factory.mktemp("db") / "t.sqlite"
    build(db)
    con = connect(db)
    r = run()
    series = r["rets"].copy()
    series["EQUAL_WEIGHT"] = r["port"]
    yield con, series
    con.close()


def q(con, sql):
    return pd.read_sql_query(sql, con)


def sqlfile(name):
    from prpa.db import SQL_DIR

    return (SQL_DIR / f"{name}.sql").read_text()


def test_returns_view_matches_pandas(env):
    con, s = env
    v = q(con, "SELECT date, ret FROM v_returns WHERE series='GLD' ORDER BY date")
    np.testing.assert_allclose(v["ret"].values, s["GLD"].values, rtol=0, atol=1e-12)


def test_monthly_compounding(env):
    con, s = env
    v = q(con, "SELECT month, ret FROM v_monthly WHERE series='EQUAL_WEIGHT' ORDER BY month")
    pdm = (1 + s["EQUAL_WEIGHT"]).groupby(s.index.to_period("M")).prod() - 1
    np.testing.assert_allclose(v["ret"].values, pdm.values, atol=1e-10)


def test_annual_vol(env):
    con, s = env
    v = q(con, "SELECT year, vol FROM v_annual WHERE series='SPY' ORDER BY year")
    pdv = s["SPY"].groupby(s.index.year).std(ddof=1) * np.sqrt(252)
    np.testing.assert_allclose(v["vol"].values, pdv.values, atol=1e-9)


@pytest.mark.parametrize("col", ["EQUAL_WEIGHT", "SPY", "TLT"])
def test_drawdown_matches_metrics(env, col):
    con, s = env
    v = q(con, f"SELECT drawdown FROM v_drawdown WHERE series='{col}' ORDER BY date")
    np.testing.assert_allclose(v["drawdown"].values, metrics.drawdown(s[col]).values, atol=1e-9)


def test_drawdown_episode_depth_is_max_drawdown(env):
    con, s = env
    ep = q(con, sqlfile("drawdown_episodes"))
    for col in ("EQUAL_WEIGHT", "SPY"):
        top = ep[(ep.series == col) & (ep.rk == 1)].iloc[0]
        dd = metrics.drawdown(s[col])
        assert top.depth_pct == pytest.approx(round(dd.min() * 100, 2))
        assert top.trough_date == str(dd.idxmin().date())


def test_rolling_vol(env):
    con, s = env
    v = q(con, sqlfile("rolling_vol_63d"))
    v = v[v.series == "SPY"].set_index("date")["vol_63d"]
    pdv = (s["SPY"].rolling(63).std(ddof=1) * np.sqrt(252)).dropna()
    np.testing.assert_allclose(v.values, pdv.values, atol=1e-8)


def test_stress_period_return(env):
    con, s = env
    v = q(con, sqlfile("stress_periods")).set_index("name")
    w = s.loc["2020-02-20":"2020-03-23", "SPY"]
    assert v.loc["COVID crash 2020", "SPY"] == pytest.approx(round(((1 + w).prod() - 1) * 100, 2))


def test_correlation_by_year(env):
    con, s = env
    v = q(con, sqlfile("stock_bond_corr_by_year")).set_index("year")
    y = s.loc["2022"]
    assert v.loc["2022", "spy_tlt_corr"] == pytest.approx(round(y["SPY"].corr(y["TLT"]), 4))


def test_hit_rate_counts(env):
    con, s = env
    v = q(con, sqlfile("monthly_hit_rate")).set_index("regime")
    m = (1 + s).groupby(s.index.to_period("M")).prod() - 1
    assert v.loc["All months", "n_months"] == len(m)
    # SPY's 2010-11 return is 0 to ~1e-16, so its sign depends on float rounding order
    down = v.loc["SPY down month", "n_months"]
    assert int((m["SPY"] < -1e-12).sum()) <= down <= int((m["SPY"] < 1e-12).sum())
    beat = (m["EQUAL_WEIGHT"] > m["SPY"]).mean()
    assert v.loc["All months", "ew_beat_rate"] == pytest.approx(round(beat, 4))
