"""Sortino, Calmar, beta and a rolling one-year comparison. Writes results/stage3.json."""

import json

from prpa import config, metrics
from prpa.analysis import run
from prpa.ingest import verify

OUT = config.ROOT / "results" / "stage3.json"
W = config.TRADING_DAYS  # 1-year rolling window


def main() -> None:
    verify()
    r = run()
    port, bench, rf = r["port"], r["bench"], r["rf"]
    rr_p, rr_b = metrics.rolling_return(port, W), metrics.rolling_return(bench, W)
    rs_p, rs_b = metrics.rolling_sharpe(port, rf, W), metrics.rolling_sharpe(bench, rf, W)
    rc = metrics.rolling_corr(port, bench, W).dropna()
    ok = rr_p.notna()
    res = {
        "period": {"first": str(port.index[0].date()), "last": str(port.index[-1].date())},
        "equal_weight": metrics.summary(port, rf) | {"beta_vs_spy": metrics.beta(port, bench)},
        "spy": metrics.summary(bench, rf),
        "rolling_1y": {
            "n_windows": int(ok.sum()),
            "ew_beat_spy_return_share": float((rr_p[ok] > rr_b[ok]).mean()),
            "ew_beat_spy_sharpe_share": float((rs_p[ok] > rs_b[ok]).mean()),
            "ew_return_min": float(rr_p.min()),
            "ew_return_min_end": str(rr_p.idxmin().date()),
            "ew_return_max": float(rr_p.max()),
            "ew_return_max_end": str(rr_p.idxmax().date()),
            "spy_return_min": float(rr_b.min()),
            "spy_return_min_end": str(rr_b.idxmin().date()),
            "spy_return_max": float(rr_b.max()),
            "spy_return_max_end": str(rr_b.idxmax().date()),
            "ew_negative_share": float((rr_p[ok] < 0).mean()),
            "spy_negative_share": float((rr_b[ok] < 0).mean()),
            "corr_ew_spy_min": float(rc.min()),
            "corr_ew_spy_min_end": str(rc.idxmin().date()),
            "corr_ew_spy_max": float(rc.max()),
            "corr_ew_spy_max_end": str(rc.idxmax().date()),
        },
    }
    OUT.write_text(json.dumps(res, indent=2) + "\n")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
