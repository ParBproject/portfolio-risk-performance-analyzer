"""The static demo site must show exactly the committed results."""

import json

import pytest

from prpa import config, site


@pytest.fixture(scope="module")
def data():
    return site.build_data()


def test_metrics_match_stage4(data):
    stage4 = json.loads((config.ROOT / "results" / "stage4.json").read_text())
    for key, label in site.LABELS.items():
        assert data["metrics"][label] == stage4[key]


def test_growth_ends_at_total_return(data):
    for label, m in data["metrics"].items():
        assert data["growth"][label][-1] == pytest.approx(1 + m["total_return"], rel=1e-6)
    assert data["growth"]["dates"][-1] == data["period"]["last"]


def test_drawdown_min_matches_max_drawdown(data):
    # weekly sampling can miss the exact trough day, so it can only be shallower
    for label, m in data["metrics"].items():
        assert min(data["drawdown"][label]) >= m["max_drawdown"] - 1e-9


def test_weights_sum_to_one(data):
    w = data["mv_weights"]
    assets = [k for k in w if k != "dates"]
    for i in range(len(w["dates"])):
        assert sum(w[a][i] for a in assets) == pytest.approx(1.0, abs=1e-5)


def test_committed_site_data_is_current(data):
    committed = json.loads((site.SITE_DIR / "data.json").read_text())
    assert committed["metrics"] == data["metrics"]
    assert committed["growth"]["dates"] == data["growth"]["dates"]
    for label in site.LABELS.values():
        assert committed["growth"][label] == pytest.approx(data["growth"][label], abs=1e-9)
