"""Clean the frozen snapshot: validate, align calendars, handle missing values."""

import numpy as np
import pandas as pd

from prpa import config


def load_raw(ticker: str) -> pd.DataFrame:
    path = config.RAW_DIR / (ticker.replace("^", "") + ".csv")
    return pd.read_csv(path, index_col="date", parse_dates=True)


def validate_prices(px: pd.DataFrame) -> None:
    """Raise if a price table breaks basic invariants."""
    if not px.index.is_monotonic_increasing:
        raise ValueError("dates not sorted")
    if px.index.has_duplicates:
        raise ValueError("duplicate dates")
    if (px <= 0).any().any():
        raise ValueError("non-positive price")
    if px.isna().any().any():
        raise ValueError("missing prices after cleaning")


def adj_close_panel(tickers=None, max_ffill: int = 3) -> tuple[pd.DataFrame, dict]:
    """Wide table of adjusted closes on dates where SPY traded.

    Gaps of up to `max_ffill` days are forward-filled (a stale price = zero return);
    anything longer is left as NaN and the row is dropped. Returns the panel and a log.
    """
    tickers = tickers or list(config.UNIVERSE)
    px = pd.concat({t: load_raw(t)["Adj Close"] for t in tickers}, axis=1)
    px = px.reindex(load_raw(config.BENCHMARK).index)
    log = {"rows_raw": int(len(px)), "missing_before": int(px.isna().sum().sum())}
    px = px.ffill(limit=max_ffill)
    log["missing_after_ffill"] = int(px.isna().sum().sum())
    px = px.dropna()
    log["rows_clean"] = int(len(px))
    validate_prices(px)
    return px, log


def risk_free_daily(index: pd.DatetimeIndex) -> pd.Series:
    """Daily risk-free return from the 13-week T-bill yield (^IRX, annual %).

    Approximation: daily rf = yield / 100 / 252, forward-filled onto the ETF calendar.
    """
    irx = load_raw(config.RISK_FREE)["Close"].reindex(index).ffill().bfill()
    rf = irx / 100.0 / config.TRADING_DAYS
    return rf.rename("rf").astype(np.float64)
