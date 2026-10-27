"""Cases for Sortino, Calmar, beta and the rolling metrics."""

import json

import numpy as np
import pandas as pd
import pytest

from prpa import config, metrics


def s(vals):
    return pd.Series(vals, index=pd.bdate_range("2020-01-01", periods=len(vals)), dtype=float)


def test_sortino_hand_case():
    # excess returns [.02, -.01, .01, -.02]: mean 0; use [.03,-.01,.01,-.01] -> mean .005
    r = s([0.03, -0.01, 0.01, -0.01])
    dd = np.sqrt((0.01**2 + 0.01**2) / 4)  # downside over ALL 4 days = sqrt(.00005)
    assert metrics.sortino(r) == pytest.approx(0.005 / dd * np.sqrt(252))


def test_sortino_with_rf_shifts_target():
    r = s([0.03, -0.01, 0.01, -0.01])
    assert metrics.sortino(r + 0.001, 0.001) == pytest.approx(metrics.sortino(r))


def test_sortino_ge_sharpe_for_symmetric_returns():
    r = s([0.01, -0.01] * 50 + [0.002])
    assert metrics.sortino(r) > metrics.sharpe(r)


def test_calmar_hand_case():
    # 504 days (2 yrs): +20%, -25%, then flat, ending +21%... build: total = 1.2*0.75*x = 1.21
    x = 1.21 / 0.9 - 1
    r = s([0.20, -0.25, x] + [0.0] * 501)
    # CAGR = sqrt(1.21) - 1 = 10%; max DD = -25% -> Calmar 0.4
    assert metrics.calmar(r) == pytest.approx(0.40)


def test_beta_hand_case():
    b = s([0.01, -0.02, 0.03, 0.0])
    assert metrics.beta(0.5 * b + 0.001, b) == pytest.approx(0.5)
    assert metrics.beta(b, b) == pytest.approx(1.0)


def test_rolling_return():
    r = s([0.10, 0.10, -0.50])
    out = metrics.rolling_return(r, 2)
    assert np.isnan(out.iloc[0])
    assert out.iloc[1] == pytest.approx(0.21)
    assert out.iloc[2] == pytest.approx(1.1 * 0.5 - 1)


def test_rolling_vol_and_sharpe_match_full_sample_on_last_window():
    r = s([0.01, -0.02, 0.015, 0.0, 0.005])
    assert metrics.rolling_vol(r, 5).iloc[-1] == pytest.approx(metrics.annualized_vol(r))
    assert metrics.rolling_sharpe(r, 0.0, 5).iloc[-1] == pytest.approx(metrics.sharpe(r))


def test_rolling_corr_perfect():
    a = s([0.01, -0.02, 0.03, 0.0])
    assert metrics.rolling_corr(a, 2 * a, 3).iloc[-1] == pytest.approx(1.0)
    assert metrics.rolling_corr(a, -a, 3).iloc[-1] == pytest.approx(-1.0)


def test_correlation_matrix_symmetric_unit_diagonal():
    df = pd.DataFrame({"a": [0.01, 0.02, -0.01], "b": [0.0, 0.01, 0.02]})
    c = metrics.correlation_matrix(df)
    assert np.allclose(np.diag(c), 1.0) and np.allclose(c, c.T)


def test_stage3_results_pinned():
    from prpa.analysis import run

    saved = json.loads((config.ROOT / "results" / "stage3.json").read_text())
    r = run()
    got = metrics.summary(r["port"], r["rf"])
    for k in ("sortino", "calmar", "sharpe", "max_drawdown"):
        assert got[k] == pytest.approx(saved["equal_weight"][k], abs=1e-10)
    rr = metrics.rolling_return(r["port"]).dropna()
    assert len(rr) == saved["rolling_1y"]["n_windows"]
    assert rr.min() == pytest.approx(saved["rolling_1y"]["ew_return_min"], abs=1e-12)
