"""Hand-checked metric cases (numbers worked out on paper in the comments)."""

import numpy as np
import pandas as pd
import pytest

from prpa import metrics


def s(vals):
    return pd.Series(vals, index=pd.bdate_range("2020-01-01", periods=len(vals)), dtype=float)


def test_cumulative_and_total():
    r = s([0.10, -0.10])  # 1.1 * 0.9 = 0.99
    assert metrics.cumulative(r).iloc[-1] == pytest.approx(0.99)
    assert metrics.total_return(r) == pytest.approx(-0.01)


def test_annualized_return_constant():
    r = s([0.001] * 252)  # one year of +0.1%/day -> 1.001^252 - 1
    assert metrics.annualized_return(r) == pytest.approx(1.001**252 - 1)


def test_annualized_return_two_years():
    r = s([0.0] * 503 + [0.21])  # +21% over 504 days (2 yrs) -> sqrt(1.21) - 1 = 10%
    assert metrics.annualized_return(r) == pytest.approx(0.10)


def test_vol():
    r = s([0.01, -0.01, 0.01, -0.01])  # sample std = sqrt(4*0.0001/3)
    assert metrics.annualized_vol(r) == pytest.approx(np.sqrt(0.0004 / 3) * np.sqrt(252))


def test_sharpe_zero_rf_and_constant_rf():
    r = s([0.02, 0.00, 0.02, 0.00])  # mean .01, std sqrt(.0004*4/3/4)... computed directly
    expected = 0.01 / r.std(ddof=1) * np.sqrt(252)
    assert metrics.sharpe(r) == pytest.approx(expected)
    # subtracting a constant rf shifts the mean only
    assert metrics.sharpe(r, 0.005) == pytest.approx(0.005 / r.std(ddof=1) * np.sqrt(252))


def test_max_drawdown_hand_case():
    # path: 1 -> 1.2 -> 0.9 -> 1.08 ; peak 1.2, trough 0.9 -> -25%
    r = s([0.20, -0.25, 0.20])
    assert metrics.max_drawdown(r) == pytest.approx(-0.25)


def test_drawdown_from_first_day_counts_initial_capital():
    r = s([-0.10, 0.05])  # lose 10% on day 1 -> -10% drawdown from starting $1
    assert metrics.max_drawdown(r) == pytest.approx(-0.10)


def test_monotone_up_no_drawdown():
    assert metrics.max_drawdown(s([0.01] * 10)) == 0.0
