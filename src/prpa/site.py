"""Write site/data.json for the static pages.

Series come from results/ and from the same helpers the Streamlit app uses.
Run: python -m prpa.site
"""

import json

import pandas as pd

from prpa import config, dashboard

SITE_DIR = config.ROOT / "site"
RESULTS = config.ROOT / "results"
KEYS = ("min_variance", "equal_weight", "spy")
LABELS = {"min_variance": "Min variance", "equal_weight": "Equal weight", "spy": "SPY"}


def _series(df: pd.DataFrame) -> dict:
    """Week-end samples of each column (keeps the page small) plus the final day."""
    weekly = df.resample("W-FRI").last()
    if weekly.index[-1] != df.index[-1]:
        weekly = pd.concat([weekly.iloc[:-1], df.iloc[[-1]]])
    weekly = weekly.dropna(how="all")
    out = {"dates": [d.strftime("%Y-%m-%d") for d in weekly.index]}
    for col in df.columns:
        out[col] = [round(float(v), 6) for v in weekly[col]]
    return out


def build_data() -> dict:
    stage4 = json.loads((RESULTS / "stage4.json").read_text())
    d = dashboard.load()
    rets = d["rets"]
    weights = pd.read_csv(RESULTS / "stage4_weights.csv", parse_dates=["date"]).set_index("date")
    stress = pd.read_csv(RESULTS / "sql" / "stress_periods.csv")
    regime = pd.read_csv(RESULTS / "sql" / "correlation_by_regime.csv")
    return {
        "period": stage4["period"],
        "assumptions": stage4["assumptions"],
        "metrics": {LABELS[k]: stage4[k] for k in KEYS},
        "growth": _series(dashboard.growth(rets)),
        "drawdown": _series(dashboard.drawdowns(rets)),
        "rolling_sharpe": _series(dashboard.rolling_sharpe(rets, d["rf"]).dropna()),
        "mv_weights": {
            "dates": [x.strftime("%Y-%m-%d") for x in weights.index],
            **{c: [round(float(v), 6) for v in weights[c]] for c in weights.columns},
        },
        "stress": stress.to_dict(orient="records"),
        "regime_corr": regime.to_dict(orient="records"),
    }


def main() -> None:
    SITE_DIR.mkdir(exist_ok=True)
    data = build_data()
    (SITE_DIR / "data.json").write_text(json.dumps(data, separators=(",", ":")) + "\n")
    print(f"wrote {SITE_DIR / 'data.json'}")


if __name__ == "__main__":
    main()
