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


def summary(r: pd.Series, rf: pd.Series | float = 0.0) -> dict:
    dd = drawdown(r)
    return {
        "total_return": total_return(r),
        "annualized_return": annualized_return(r),
        "annualized_vol": annualized_vol(r),
        "sharpe": sharpe(r, rf),
        "max_drawdown": float(dd.min()),
        "max_drawdown_trough": str(dd.idxmin().date()) if hasattr(dd.idxmin(), "date") else None,
    }
