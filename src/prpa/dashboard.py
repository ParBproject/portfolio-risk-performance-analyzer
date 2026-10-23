"""Pure data helpers for the Streamlit app (kept out of the UI file so they can be tested).

All strategies run continuously over the common period (from the first full min-variance
estimation window). The date filter slices those return series; it does not restart them.
"""

from functools import lru_cache

import pandas as pd

from prpa import config, metrics

STRATEGIES = ("Min variance", "Equal weight", "SPY")
SQL_DIR = config.ROOT / "results" / "sql"
METRIC_COLS = {
    "total_return": "Total return",
    "annualized_return": "Ann. return",
    "annualized_vol": "Ann. vol",
    "sharpe": "Sharpe",
    "sortino": "Sortino",
    "max_drawdown": "Max DD",
    "calmar": "Calmar",
}


@lru_cache(maxsize=1)
def load() -> dict:
    """Strategy returns, risk-free series and weight histories on the common period."""
    from prpa.stage4 import compute

    c = compute()
    idx = c["mv"].index
    rets = pd.DataFrame({"Min variance": c["mv"], "Equal weight": c["ew"], "SPY": c["spy"]})
    ew_w = pd.DataFrame(1 / c["rets"].shape[1], index=c["mv_w"].index, columns=c["rets"].columns)
    spy_w = pd.DataFrame(0.0, index=c["mv_w"].index, columns=c["rets"].columns)
    spy_w[config.BENCHMARK] = 1.0
    return {
        "rets": rets,
        "rf": c["rf"].reindex(idx),
        "asset_rets": c["rets"].loc[idx],
        "weights": {"Min variance": c["mv_w"], "Equal weight": ew_w, "SPY": spy_w},
    }


def filter_dates(df, start, end):
    """Inclusive date slice; raises if empty or reversed."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    if start > end:
        raise ValueError("start must be on or before end")
    out = df.loc[start:end]
    if len(out) == 0:
        raise ValueError("no data in the selected range")
    return out


def growth(rets: pd.DataFrame) -> pd.DataFrame:
    """Growth of $1 from the first selected day."""
    return (1 + rets).cumprod()


def drawdowns(rets: pd.DataFrame) -> pd.DataFrame:
    return rets.apply(metrics.drawdown)


def rolling_sharpe(rets: pd.DataFrame, rf: pd.Series, window: int = 252) -> pd.DataFrame:
    return rets.apply(lambda s: metrics.rolling_sharpe(s, rf.loc[s.index], window)).dropna(
        how="all"
    )


def risk_table(rets: pd.DataFrame, rf: pd.Series) -> pd.DataFrame:
    """One row per strategy, metrics as columns (needs >= 2 days)."""
    if len(rets) < 2:
        raise ValueError("need at least 2 days")
    rows = {s: metrics.summary(rets[s], rf.loc[rets.index]) for s in rets.columns}
    t = pd.DataFrame(rows).T[list(METRIC_COLS)].astype(float)
    return t.rename(columns=METRIC_COLS)


def weights_as_of(weights: pd.DataFrame, date) -> tuple[pd.Timestamp, pd.Series]:
    """Most recent target weights set on or before `date` (the ones in force next day)."""
    past = weights.loc[: pd.Timestamp(date)]
    if past.empty:
        raise ValueError("no weights on or before this date")
    return past.index[-1], past.iloc[-1]


def sql_result(name: str) -> pd.DataFrame:
    """A saved SQL query result from results/sql (written by scripts/run_queries.py)."""
    return pd.read_csv(SQL_DIR / f"{name}.csv")


def stress_table() -> pd.DataFrame:
    df = sql_result("stress_periods").set_index("name")
    return df.rename(columns={"EW": "Equal weight"})


def regime_corr() -> pd.DataFrame:
    df = sql_result("correlation_by_regime")
    return df.pivot(index="other", columns="regime", values="corr")[["calm", "stress"]]
