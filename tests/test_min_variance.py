"""Minimum-variance optimiser and the time-varying backtest."""

import json

import numpy as np
import pandas as pd
import pytest

from prpa import config
from prpa.optimize import min_variance, rolling_min_variance
from prpa.portfolio import backtest_weights


def test_two_asset_hand_case():
    # vols 10% and 20%, corr 0: w1 = s2^2/(s1^2+s2^2) = .04/.05 = 0.8
    cov = np.array([[0.01, 0.0], [0.0, 0.04]])
    np.testing.assert_allclose(min_variance(cov), [0.8, 0.2])


def test_two_asset_with_correlation_hand_case():
    # s1=.1, s2=.2, rho=.5 -> cov12=.01; w1 = (s2^2-c)/(s1^2+s2^2-2c) = .03/.03 = 1.0
    cov = np.array([[0.01, 0.01], [0.01, 0.04]])
    np.testing.assert_allclose(min_variance(cov), [1.0, 0.0], atol=1e-12)


def test_long_only_binds_when_unconstrained_wants_short():
    # rho=.9: unconstrained w1 = (.04-.018)/(.05-.036) > 1 -> long-only gives [1, 0]
    cov = np.array([[0.01, 0.018], [0.018, 0.04]])
    np.testing.assert_allclose(min_variance(cov), [1.0, 0.0], atol=1e-12)


def test_matches_brute_force_grid_three_assets():
    rng = np.random.default_rng(0)
    a = rng.normal(size=(3, 3))
    cov = a @ a.T + 0.1 * np.eye(3)
    w = min_variance(cov)
    grid = [
        (x, y, 1 - x - y)
        for x in np.linspace(0, 1, 201)
        for y in np.linspace(0, 1, 201)
        if x + y <= 1 + 1e-12
    ]
    best = min(np.array(g) @ cov @ np.array(g) for g in grid)
    assert w @ cov @ w <= best + 1e-12


@pytest.fixture(scope="module")
def real():
    from prpa.analysis import run

    rets = run()["rets"]
    return rets, rolling_min_variance(rets)


def test_real_weights_sum_to_one_and_non_negative(real):
    _, w = real
    np.testing.assert_allclose(w.sum(axis=1), 1.0, atol=1e-12)
    assert (w >= 0).all().all()


def test_first_estimate_needs_full_window(real):
    rets, w = real
    assert rets.index.get_loc(w.index[0]) + 1 >= 252


def test_no_lookahead_future_data_does_not_change_weights(real):
    rets, w = real
    cut = w.index[100]
    later = rets.copy()
    later.loc[later.index > cut] *= -3.0  # scramble everything after the cut
    w2 = rolling_min_variance(later)
    pd.testing.assert_frame_equal(w.loc[:cut], w2.loc[:cut])


def test_backtest_applies_weights_next_day():
    idx = pd.bdate_range("2021-01-27", periods=4)  # 27, 28, 29 (month end), Feb 1
    rets = pd.DataFrame(
        [[0.0, 0.0], [0.1, 0.0], [0.0, 0.0], [0.0, 0.1]], index=idx, columns=["A", "B"]
    )
    wts = pd.DataFrame([[1.0, 0.0], [0.0, 1.0]], index=[idx[0], idx[2]], columns=["A", "B"])
    net, log = backtest_weights(rets, wts, cost_bps=0)
    assert net.index[0] == idx[1]  # invested at close of idx[0]
    assert net.loc[idx[1]] == pytest.approx(0.1)  # held A
    assert net.loc[idx[3]] == pytest.approx(0.1)  # switched to B at close of idx[2]
    assert log.loc[idx[2], "turnover"] == pytest.approx(2.0)


def test_backtest_rejects_bad_weights():
    idx = pd.bdate_range("2021-01-27", periods=2)
    rets = pd.DataFrame(0.0, index=idx, columns=["A", "B"])
    with pytest.raises(ValueError):
        backtest_weights(rets, pd.DataFrame([[1.2, -0.2]], index=[idx[0]], columns=["A", "B"]))


def test_stage4_results_pinned():
    from prpa import metrics
    from prpa.stage4 import compute

    saved = json.loads((config.ROOT / "results" / "stage4.json").read_text())
    c = compute()
    for key, ser in (("min_variance", c["mv"]), ("equal_weight", c["ew"]), ("spy", c["spy"])):
        got = metrics.summary(ser, c["rf"])
        for k in ("annualized_return", "annualized_vol", "sharpe", "max_drawdown"):
            assert got[k] == pytest.approx(saved[key][k], abs=1e-10)
    assert c["mv_log"]["cost"].sum() == pytest.approx(
        saved["turnover"]["min_variance"]["total_cost"], abs=1e-12
    )
