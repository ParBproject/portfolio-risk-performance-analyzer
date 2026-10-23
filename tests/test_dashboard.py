"""Dashboard helpers and an AppTest smoke test."""

import pandas as pd
import pytest

from prpa import dashboard, metrics


@pytest.fixture(scope="module")
def d():
    return dashboard.load()


def test_load_shapes(d):
    assert list(d["rets"].columns) == list(dashboard.STRATEGIES)
    assert d["rets"].index[0] == pd.Timestamp("2007-02-01")
    assert d["rf"].notna().all()
    for w in d["weights"].values():
        assert (w.sum(axis=1) - 1).abs().max() < 1e-12


def test_filter_dates_inclusive_and_errors(d):
    out = dashboard.filter_dates(d["rets"], "2020-03-02", "2020-03-06")
    assert out.index[0] == pd.Timestamp("2020-03-02") and len(out) == 5
    with pytest.raises(ValueError):
        dashboard.filter_dates(d["rets"], "2020-03-06", "2020-03-02")
    with pytest.raises(ValueError):
        dashboard.filter_dates(d["rets"], "2030-01-01", "2030-02-01")


def test_growth_and_drawdown_hand_case():
    r = pd.DataFrame({"x": [0.2, -0.25, 0.2]}, index=pd.bdate_range("2021-01-01", periods=3))
    assert dashboard.growth(r)["x"].iloc[-1] == pytest.approx(1.08)
    assert dashboard.drawdowns(r)["x"].min() == pytest.approx(-0.25)


def test_risk_table_matches_metrics(d):
    r = dashboard.filter_dates(d["rets"], "2010-01-01", "2014-12-31")
    t = dashboard.risk_table(r, d["rf"])
    assert list(t.index) == list(dashboard.STRATEGIES)
    assert t.loc["SPY", "Sharpe"] == pytest.approx(metrics.sharpe(r["SPY"], d["rf"].loc[r.index]))
    with pytest.raises(ValueError):
        dashboard.risk_table(r.iloc[:1], d["rf"])


def test_full_period_table_matches_stage4_json(d):
    import json

    from prpa import config

    s4 = json.loads((config.ROOT / "results" / "stage4.json").read_text())
    t = dashboard.risk_table(d["rets"], d["rf"])
    assert t.loc["Min variance", "Sharpe"] == pytest.approx(s4["min_variance"]["sharpe"])


def test_weights_as_of(d):
    w = d["weights"]["Min variance"]
    when, cur = dashboard.weights_as_of(w, "2020-03-15")
    assert when == pd.Timestamp("2020-02-28")
    assert cur.sum() == pytest.approx(1.0)
    with pytest.raises(ValueError):
        dashboard.weights_as_of(w, "2000-01-01")


def test_rolling_sharpe_needs_full_window(d):
    r = dashboard.filter_dates(d["rets"], "2020-01-01", "2020-06-30")
    assert len(dashboard.rolling_sharpe(r, d["rf"])) == 0


def test_sql_views_load():
    s = dashboard.stress_table()
    assert "COVID crash 2020" in s.index and "Equal weight" in s.columns
    rc = dashboard.regime_corr()
    assert list(rc.columns) == ["calm", "stress"] and len(rc) == 5


def test_app_smoke():
    from streamlit.testing.v1 import AppTest

    from prpa import config

    at = AppTest.from_file(str(config.ROOT / "app" / "streamlit_app.py"), default_timeout=120).run()
    assert not at.exception
    assert len(at.tabs) == 3
    assert any("Risk summary" in s.value for s in at.subheader)
    at.sidebar.multiselect[0].set_value(["SPY"]).run()
    assert not at.exception
    at.sidebar.multiselect[0].set_value([]).run()
    assert at.warning
