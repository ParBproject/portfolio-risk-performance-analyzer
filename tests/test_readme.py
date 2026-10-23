"""Headline README numbers must match the results files they cite."""

import json

import pandas as pd
import pytest

from prpa import config

R = config.ROOT / "results"
README = (config.ROOT / "README.md").read_text()


def j(name):
    return json.loads((R / name).read_text())


def pct(x, nd=2):
    return f"{x * 100:.{nd}f}%".replace("-", "−")


@pytest.mark.parametrize(
    "text",
    [
        pct(j("stage1.json")["equal_weight"]["annualized_return"]),
        pct(j("stage1.json")["spy"]["annualized_return"]),
        pct(j("stage1.json")["equal_weight"]["annualized_vol"]),
        pct(j("stage1.json")["spy"]["annualized_vol"]),
        pct(j("stage1.json")["equal_weight"]["max_drawdown"], 1),
        pct(j("stage1.json")["spy"]["max_drawdown"], 1),
        pct(j("stage1.json")["equal_weight"]["total_return"], 1),
        pct(j("stage1.json")["avg_risk_free_annual"]),
        pct(j("stage4.json")["min_variance"]["annualized_return"]),
        pct(j("stage4.json")["min_variance"]["annualized_vol"]),
        pct(j("stage4.json")["equal_weight"]["annualized_return"]),
        pct(j("stage4.json")["spy"]["annualized_return"]),
        pct(j("stage4.json")["min_variance"]["max_drawdown"], 1),
        pct(j("stage4.json")["mv_weights"]["average"]["AGG"], 1),
        pct(j("stage4.json")["turnover"]["min_variance"]["total_cost"]),
        pct(j("stage3.json")["rolling_1y"]["ew_beat_spy_return_share"], 1),
        pct(j("stage3.json")["rolling_1y"]["ew_beat_spy_sharpe_share"], 1),
        pct(j("stage3.json")["rolling_1y"]["ew_return_min"], 1),
        pct(j("stage3.json")["rolling_1y"]["spy_return_max"], 1).replace("77.5%", "+77.5%"),
    ],
)
def test_number_in_readme(text):
    assert text in README


@pytest.mark.parametrize(
    "key,val",
    [
        (("stage1.json", "equal_weight", "sharpe"), "0.52"),
        (("stage1.json", "spy", "sharpe"), "0.55"),
        (("stage3.json", "equal_weight", "sortino"), "0.73"),
        (("stage3.json", "equal_weight", "calmar"), "0.22"),
        (("stage4.json", "min_variance", "sharpe"), "0.35"),
        (("stage4.json", "min_variance", "beta_vs_spy"), "0.09"),
    ],
)
def test_ratio_in_readme(key, val):
    f, a, b = key
    assert f"{j(f)[a][b]:.2f}" == val and val in README


def test_sql_numbers_in_readme():
    h = pd.read_csv(R / "sql" / "monthly_hit_rate.csv").set_index("regime")
    assert pct(h.loc["All months", "ew_beat_rate"], 1) in README
    assert f"{int(h.loc['All months', 'n_months'])} months" in README
    e = pd.read_csv(R / "sql" / "drawdown_episodes.csv")
    spy1 = e[(e.series == "SPY") & (e.rk == 1)].iloc[0]
    assert f"{spy1.days_peak_to_recovery:,} days" in README
    s = pd.read_csv(R / "sql" / "stress_periods.csv").set_index("name")
    assert pct(s.loc["2022 rate shock", "EW"] / 100, 1) in README
    a = pd.read_csv(R / "sql" / "annual_summary.csv")
    assert f"{int((a.diff_pct > 0).sum())} of {len(a)} years" in README
