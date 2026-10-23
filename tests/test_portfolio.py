import pandas as pd
import pytest

from prpa.portfolio import backtest, equal_weights, rebalance_dates


def frame(rows, start="2021-01-27"):
    idx = pd.bdate_range(start, periods=len(rows))
    return pd.DataFrame(rows, index=idx, columns=["A", "B"], dtype=float)


def test_rebalance_dates_last_trading_day():
    idx = pd.bdate_range("2021-01-25", "2021-02-03")
    assert list(rebalance_dates(idx)) == [pd.Timestamp("2021-01-29"), pd.Timestamp("2021-02-03")]


def test_zero_cost_one_day():
    rets = frame([[0.10, 0.00]])
    net, _ = backtest(rets, equal_weights("AB"), cost_bps=0)
    assert net.iloc[0] == pytest.approx(0.05)


def test_drift_then_rebalance_cost_hand_case():
    # 2021-01-27 (Wed), 28, 29 (month end, rebalance), Feb 1
    rets = frame([[0.10, -0.10], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0]])
    net, log = backtest(rets, equal_weights("AB"), cost_bps=10)
    # day 1: gross 0; weights drift to .55/.45; initial cost 10bp on 100% turnover
    assert net.iloc[0] == pytest.approx(-0.001)
    assert net.iloc[1] == pytest.approx(0.0)
    # day 3 rebalance: turnover |.5-.55|+|.5-.45| = 0.10 -> cost 0.10 * 10bp = 1bp
    assert log.loc[pd.Timestamp("2021-01-29"), "turnover"] == pytest.approx(0.10)
    assert net.iloc[2] == pytest.approx(-0.0001)
    assert net.iloc[3] == pytest.approx(0.0)


def test_weights_must_sum_to_one():
    with pytest.raises(ValueError):
        backtest(frame([[0.0, 0.0]]), pd.Series({"A": 0.6, "B": 0.6}))


def test_no_lookahead_future_return_does_not_change_past():
    a = frame([[0.01, 0.02], [0.03, -0.01], [0.0, 0.0]])
    b = a.copy()
    b.iloc[2] = [0.5, -0.5]
    na, _ = backtest(a, equal_weights("AB"))
    nb, _ = backtest(b, equal_weights("AB"))
    pd.testing.assert_series_equal(na.iloc[:2], nb.iloc[:2])
