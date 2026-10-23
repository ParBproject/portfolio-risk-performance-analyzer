"""Equal-weight portfolio with periodic rebalancing and explicit transaction costs."""

import numpy as np
import pandas as pd


def rebalance_dates(index: pd.DatetimeIndex, freq: str = "M") -> pd.DatetimeIndex:
    """Last trading day of each period that is actually in `index`."""
    s = pd.Series(index, index=index)
    key = index.to_period(freq)
    return pd.DatetimeIndex(s.groupby(key).max().values)


def backtest(
    returns: pd.DataFrame, target: pd.Series, cost_bps: float = 10.0, freq: str = "M"
) -> tuple[pd.Series, pd.DataFrame]:
    """Daily portfolio returns, net of costs.

    Day 0 we buy the target weights (paying cost on 100% turnover). Weights then drift with
    prices. At the close of each rebalance date we trade back to target and pay
    cost_bps * one-way turnover, deducted from that day's return. No lookahead: weights
    used on day t are set from information at the close of day t-1.
    Returns (net daily returns, log of each rebalance with turnover and cost).
    """
    target = target.reindex(returns.columns).astype(float)
    if target.isna().any() or abs(target.sum() - 1) > 1e-9:
        raise ValueError("target weights must sum to 1")
    rdates = set(rebalance_dates(returns.index, freq))
    c = cost_bps / 1e4
    w = target.copy()
    out, log = [], []
    first = True
    for d, r in returns.iterrows():
        gross = float((w * r).sum())
        w = w * (1 + r) / (1 + gross)  # drift to end-of-day weights
        cost = 0.0
        if first:
            cost = c * 1.0  # initial purchase
            log.append((d, 1.0, cost))
            first = False
        if d in rdates:
            turnover = float((target - w).abs().sum())
            cost += c * turnover
            log.append((d, turnover, c * turnover))
            w = target.copy()
        out.append((1 + gross) * (1 - cost) - 1)
    net = pd.Series(out, index=returns.index, name="portfolio")
    return net, pd.DataFrame(log, columns=["date", "turnover", "cost"]).set_index("date")


def equal_weights(tickers) -> pd.Series:
    tickers = list(tickers)
    return pd.Series(1.0 / len(tickers), index=tickers)


def backtest_weights(
    returns: pd.DataFrame, weights: pd.DataFrame, cost_bps: float = 10.0
) -> tuple[pd.Series, pd.DataFrame]:
    """Backtest time-varying targets set at the close of each date in `weights.index`.

    Invests at the close of the first weight date (cost on 100% turnover, charged on the
    first return day), so returns start the NEXT trading day. At each later weight date,
    trades from drifted weights to the new target, paying cost_bps * one-way turnover.
    """
    if (weights < -1e-12).any().any() or not np.allclose(weights.sum(axis=1), 1.0):
        raise ValueError("weights must be non-negative and sum to 1")
    c = cost_bps / 1e4
    start = weights.index[0]
    rets = returns.loc[returns.index > start, weights.columns]
    w = weights.iloc[0].astype(float)
    targets = {d: weights.loc[d].astype(float) for d in weights.index[1:]}
    out, log = [], []
    for i, (d, r) in enumerate(rets.iterrows()):
        gross = float((w * r).sum())
        w = w * (1 + r) / (1 + gross)
        cost = 0.0
        if i == 0:
            cost = c
            log.append((d, 1.0, c))
        if d in targets:
            turnover = float((targets[d] - w).abs().sum())
            cost += c * turnover
            log.append((d, turnover, c * turnover))
            w = targets[d]
        out.append((1 + gross) * (1 - cost) - 1)
    net = pd.Series(out, index=rets.index, name="portfolio")
    return net, pd.DataFrame(log, columns=["date", "turnover", "cost"]).set_index("date")
