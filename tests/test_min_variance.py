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


def test_two_asset_interior_correlation_hand_case():
    # s1^2=.04, s2^2=.01, c=.005 -> w1 = (.01-.005)/(.04+.01-2*.005) = .005/.04 = .125
    cov = np.array([[0.04, 0.005], [0.005, 0.01]])
    np.testing.assert_allclose(min_variance(cov), [0.125, 0.875])


def test_three_uncorrelated_assets_closed_form():
    # w_i ∝ 1/σ_i^2 with σ^2 = .01, .04, .16 -> 100, 25, 6.25 over 131.25
    cov = np.diag([0.01, 0.04, 0.16])
    np.testing.assert_allclose(min_variance(cov), np.array([100, 25, 6.25]) / 131.25)


def test_riskless_asset_takes_the_whole_portfolio():
    # The second asset is riskless, so its covariance row is 0. Long-only GMV is 100% there.
    cov = np.array([[0.04, 0.0], [0.0, 0.0]])
    w = min_variance(cov)
    np.testing.assert_allclose(w, [0.0, 1.0], atol=1e-12)
    assert float(w @ cov @ w) == pytest.approx(0.0, abs=1e-12)


def test_perfect_positive_correlation_rejects_the_short():
    # σ1=.2, σ2=.4, corr=+1. Σ = [[.04, .08], [.08, .16]] = .04 * [[1, 2], [2, 4]].
    # Fully invested critical point is [2, -1], and [2, -1] @ Σ @ [2, -1] = 0.
    # That short is not allowed. On w2=1-w1, variance = .04 * (2 - w1)^2,
    # smallest for w1 in [0, 1] at w1=1: weights [1, 0], variance .04.
    cov = np.array([[0.04, 0.08], [0.08, 0.16]])
    short = np.array([2.0, -1.0])
    assert float(short @ cov @ short) == pytest.approx(0.0, abs=1e-12)
    w = min_variance(cov)
    np.testing.assert_allclose(w, [1.0, 0.0], atol=1e-12)
    assert float(w @ cov @ w) == pytest.approx(0.04)


def test_zero_inverse_sum_skips_the_full_set():
    # Σ = diag(1, 1, -1/2), symmetric and invertible. Σ^{-1} 1 = [1, 1, -2]
    # sums to 0, so the full set is not divided through. The third asset has
    # variance -1/2 and is not used. The first two are 50/50 with variance 1/2,
    # which is below either of those singletons (variance 1).
    cov = np.diag([1.0, 1.0, -0.5])
    x = np.linalg.solve(cov, np.ones(3))
    np.testing.assert_allclose(x, [1.0, 1.0, -2.0])
    assert float(x.sum()) == pytest.approx(0.0, abs=1e-12)
    w = min_variance(cov)
    np.testing.assert_allclose(w, [0.5, 0.5, 0.0], atol=1e-12)
    assert float(w @ cov @ w) == pytest.approx(0.5)


def test_small_inverse_sum_keeps_the_normalized_solution():
    # Σ = 1e16 I. Σ^{-1} 1 = 1e-16 * [1, 1], which sums to 2e-16. The normalized
    # weights are still [1/2, 1/2], and that variance is half of either asset alone.
    cov = 1e16 * np.eye(2)
    x = np.linalg.solve(cov, np.ones(2))
    assert abs(float(x.sum())) < 1e-12
    np.testing.assert_allclose(min_variance(cov), [0.5, 0.5])


def test_perfect_hedge_splits_evenly():
    # Σ = v [[1, -1], [-1, 1]] (perfect negative hedge). w = [1/2, 1/2] has variance 0,
    # against v for either asset alone.
    cov = np.array([[0.04, -0.04], [-0.04, 0.04]])
    w = min_variance(cov)
    np.testing.assert_allclose(w, [0.5, 0.5], atol=1e-12)
    assert float(w @ cov @ w) == pytest.approx(0.0, abs=1e-12)


def test_hedge_gets_nothing_from_an_extra_risky_asset():
    # Assets 1 and 2 cancel; asset 3 is uncorrelated with variance .09.
    # w = [1/2, 1/2, 0] has variance 0, so the risky asset is not held.
    cov = np.array([[0.04, -0.04, 0.0], [-0.04, 0.04, 0.0], [0.0, 0.0, 0.09]])
    w = min_variance(cov)
    np.testing.assert_allclose(w, [0.5, 0.5, 0.0], atol=1e-12)
    assert float(w @ cov @ w) == pytest.approx(0.0, abs=1e-12)


def test_all_riskless_assets_are_feasible():
    # Every fully invested portfolio has variance 0. Skipping the singular blocks used to
    # return None; any long-only weights that sum to 1 are optimal.
    cov = np.zeros((3, 3))
    w = min_variance(cov)
    assert w.sum() == pytest.approx(1.0)
    assert (w >= -1e-12).all()
    assert float(w @ cov @ w) == pytest.approx(0.0, abs=1e-12)


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


def test_rolling_window_is_the_trailing_year_ending_that_day():
    # Each month-end row is the minimum-variance portfolio of the 252 returns ending
    # that day (inclusive). Shifting the window by one day would change the covariance.
    idx = pd.bdate_range("2018-01-01", periods=400)
    rng = np.random.default_rng(0)
    rets = pd.DataFrame(rng.normal(0, [0.01, 0.02], size=(400, 2)), index=idx, columns=["A", "B"])
    w = rolling_min_variance(rets, window=252)
    assert len(w) > 0
    for d, row in w.iterrows():
        i = rets.index.get_loc(d)
        hist = rets.iloc[i - 251 : i + 1]
        assert len(hist) == 252 and hist.index[-1] == d
        expected = min_variance(hist.cov().values)
        np.testing.assert_allclose(row.to_numpy(), expected, atol=1e-12)


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
