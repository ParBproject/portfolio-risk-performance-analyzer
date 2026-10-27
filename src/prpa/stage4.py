"""Rolling minimum-variance vs equal weight vs SPY. Writes results/stage4.json.

The three series share dates, starting the day after the first month-end with a
full 252-day covariance window.
"""

import json

import pandas as pd

from prpa import config, metrics
from prpa.analysis import run
from prpa.ingest import verify
from prpa.optimize import WINDOW, rolling_min_variance
from prpa.portfolio import backtest_weights

OUT = config.ROOT / "results" / "stage4.json"
WEIGHTS_CSV = config.ROOT / "results" / "stage4_weights.csv"


def compute():
    r = run()
    rets, rf = r["rets"], r["rf"]
    mv_w = rolling_min_variance(rets, WINDOW)
    ew_w = pd.DataFrame(1 / rets.shape[1], index=mv_w.index, columns=rets.columns)
    mv, mv_log = backtest_weights(rets, mv_w, config.COST_BPS)
    ew, ew_log = backtest_weights(rets, ew_w, config.COST_BPS)
    spy = rets.loc[mv.index, config.BENCHMARK]
    return {
        "rets": rets,
        "rf": rf.loc[mv.index],
        "mv": mv,
        "ew": ew,
        "spy": spy,
        "mv_w": mv_w,
        "mv_log": mv_log,
        "ew_log": ew_log,
    }


def turnover_stats(log: pd.DataFrame, years: float) -> dict:
    reb = log.iloc[1:]  # exclude initial purchase
    return {
        "n_rebalances": len(reb),
        "avg_turnover": float(reb["turnover"].mean()),
        "max_turnover": float(reb["turnover"].max()),
        "annual_turnover": float(reb["turnover"].sum() / years),
        "total_cost": float(log["cost"].sum()),
        "annual_cost_drag": float(log["cost"].sum() / years),
    }


def main() -> None:
    verify()
    c = compute()
    years = len(c["mv"]) / config.TRADING_DAYS
    w = c["mv_w"]
    res = {
        "period": {
            "first": str(c["mv"].index[0].date()),
            "last": str(c["mv"].index[-1].date()),
            "n_days": len(c["mv"]),
        },
        "assumptions": {
            "window_days": WINDOW,
            "covariance": "sample, daily returns",
            "constraints": "long-only, fully invested",
            "rebalance": "monthly",
            "cost_bps_one_way": config.COST_BPS,
        },
        "min_variance": metrics.summary(c["mv"], c["rf"])
        | {"beta_vs_spy": metrics.beta(c["mv"], c["spy"])},
        "equal_weight": metrics.summary(c["ew"], c["rf"])
        | {"beta_vs_spy": metrics.beta(c["ew"], c["spy"])},
        "spy": metrics.summary(c["spy"], c["rf"]),
        "turnover": {
            "min_variance": turnover_stats(c["mv_log"], years),
            "equal_weight": turnover_stats(c["ew_log"], years),
        },
        "mv_weights": {
            "average": w.mean().to_dict(),
            "min": w.min().to_dict(),
            "max": w.max().to_dict(),
            "latest_date": str(w.index[-1].date()),
            "latest": w.iloc[-1].to_dict(),
            "avg_n_holdings_over_1pct": float((w > 0.01).sum(axis=1).mean()),
        },
    }
    OUT.write_text(json.dumps(res, indent=2) + "\n")
    w.round(6).to_csv(WEIGHTS_CSV, index_label="date")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
