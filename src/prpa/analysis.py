"""Equal-weight ETF portfolio vs SPY. Writes results/stage1.json."""

import json

from prpa import config, metrics
from prpa.clean import adj_close_panel, risk_free_daily
from prpa.ingest import verify
from prpa.portfolio import backtest, equal_weights


def run(start=None, end=None) -> dict:
    px, log = adj_close_panel()
    rets = px.pct_change().dropna()
    if start or end:
        rets = rets.loc[start:end]
    rf = risk_free_daily(rets.index)
    port, rebal = backtest(rets, equal_weights(rets.columns), config.COST_BPS, config.REBALANCE)
    bench = rets[config.BENCHMARK]
    return {"rets": rets, "rf": rf, "port": port, "bench": bench, "rebal": rebal, "log": log}


def main() -> None:
    verify()
    r = run()
    rets, rf, port, bench, rebal = r["rets"], r["rf"], r["port"], r["bench"], r["rebal"]
    res = {
        "period": {
            "first_return_date": str(rets.index[0].date()),
            "last_date": str(rets.index[-1].date()),
            "n_days": len(rets),
        },
        "assumptions": {
            "universe": config.UNIVERSE,
            "weights": "equal (1/6 each)",
            "rebalance": "monthly, last trading day",
            "cost_bps_one_way": config.COST_BPS,
            "risk_free": "13-week T-bill (^IRX) / 100 / 252, daily",
        },
        "cleaning": r["log"],
        "avg_risk_free_annual": float(rf.mean() * config.TRADING_DAYS),
        "equal_weight": metrics.summary(port, rf),
        "spy": metrics.summary(bench, rf),
        "per_asset": {t: metrics.summary(rets[t], rf) for t in rets.columns},
        "correlation_daily": rets.corr().round(4).to_dict(),
        "corr_portfolio_spy": float(port.corr(bench)),
        "rebalances": len(rebal) - 1,
        "avg_monthly_turnover": float(rebal["turnover"].iloc[1:].mean()),
        "total_cost_drag_approx": float(rebal["cost"].sum()),
    }
    config.RESULTS.parent.mkdir(exist_ok=True)
    config.RESULTS.write_text(json.dumps(res, indent=2) + "\n")
    print(json.dumps({k: res[k] for k in ("period", "equal_weight", "spy")}, indent=2))


if __name__ == "__main__":
    main()
