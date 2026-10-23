"""Performance and risk metrics. All inputs are simple (not log) daily returns."""

import numpy as np
import pandas as pd

from prpa.config import TRADING_DAYS


def cumulative(r: pd.Series) -> pd.Series:
    """Growth of $1: product of (1 + r)."""
    return (1 + r).cumprod()


def total_return(r: pd.Series) -> float:
    return float((1 + r).prod() - 1)


def annualized_return(r: pd.Series) -> float:
    """Geometric (CAGR): (1 + total)^(252 / n) - 1."""
    return float((1 + r).prod() ** (TRADING_DAYS / len(r)) - 1)


def annualized_vol(r: pd.Series) -> float:
    """Sample std of daily returns times sqrt(252)."""
    return float(r.std(ddof=1) * np.sqrt(TRADING_DAYS))


def sharpe(r: pd.Series, rf: pd.Series | float = 0.0) -> float:
    """Annualized Sharpe: mean daily excess return / its std, times sqrt(252)."""
    ex = r - rf
    return float(ex.mean() / ex.std(ddof=1) * np.sqrt(TRADING_DAYS))


def drawdown(r: pd.Series) -> pd.Series:
    """Percent below the running peak of the growth curve (0 at new highs)."""
    w = cumulative(r)
    peak = np.maximum(w.cummax(), 1.0)  # starting capital counts as a peak
    return w / peak - 1


def max_drawdown(r: pd.Series) -> float:
    return float(drawdown(r).min())


def sortino(r: pd.Series, rf: pd.Series | float = 0.0) -> float:
    """Annualized Sortino: mean daily excess return / downside deviation, times sqrt(252).

    Downside deviation = sqrt(mean(min(excess, 0)^2)) over ALL days (target = risk-free),
    so up days count as zero rather than being dropped.
    """
    ex = r - rf
    dd = np.sqrt((np.minimum(ex, 0.0) ** 2).mean())
    return float(ex.mean() / dd * np.sqrt(TRADING_DAYS))


def calmar(r: pd.Series) -> float:
    """Annualized (geometric) return / |max drawdown| over the same sample."""
    return float(annualized_return(r) / abs(max_drawdown(r)))


def beta(r: pd.Series, bench: pd.Series) -> float:
    """OLS slope of r on the benchmark: cov(r, b) / var(b)."""
    return float(r.cov(bench) / bench.var())


def correlation_matrix(rets: pd.DataFrame) -> pd.DataFrame:
    """Pearson correlation of daily returns."""
    return rets.corr()


def rolling_return(r: pd.Series, window: int = TRADING_DAYS) -> pd.Series:
    """Compounded return over each trailing window (NaN until the window is full)."""
    return (1 + r).rolling(window).apply(np.prod, raw=True) - 1


def rolling_vol(r: pd.Series, window: int = 63) -> pd.Series:
    return r.rolling(window).std(ddof=1) * np.sqrt(TRADING_DAYS)


def rolling_sharpe(
    r: pd.Series, rf: pd.Series | float = 0.0, window: int = TRADING_DAYS
) -> pd.Series:
    ex = r - rf
    return ex.rolling(window).mean() / ex.rolling(window).std(ddof=1) * np.sqrt(TRADING_DAYS)


def rolling_corr(a: pd.Series, b: pd.Series, window: int = TRADING_DAYS) -> pd.Series:
    return a.rolling(window).corr(b)


def summary(r: pd.Series, rf: pd.Series | float = 0.0) -> dict:
    dd = drawdown(r)
    return {
        "total_return": total_return(r),
        "annualized_return": annualized_return(r),
        "annualized_vol": annualized_vol(r),
        "sharpe": sharpe(r, rf),
        "sortino": sortino(r, rf),
        "max_drawdown": float(dd.min()),
        "calmar": calmar(r),
        "max_drawdown_trough": str(dd.idxmin().date()) if hasattr(dd.idxmin(), "date") else None,
    }
