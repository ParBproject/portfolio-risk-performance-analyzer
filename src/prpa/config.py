"""Single place for every assumption, so each one is explicit and easy to defend."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "prices.sqlite"
MANIFEST = ROOT / "data" / "manifest.json"
RESULTS = ROOT / "results" / "stage1.json"

# Diversified universe: one ETF per major asset class.
UNIVERSE = {
    "SPY": "US large-cap equity",
    "EFA": "Developed ex-US equity",
    "AGG": "US aggregate investment-grade bonds",
    "TLT": "Long-term US Treasuries",
    "GLD": "Gold",
    "VNQ": "US real estate (REITs)",
}
BENCHMARK = "SPY"
RISK_FREE = "^IRX"  # 13-week US T-bill yield (annualized %, discount basis)

START = "2006-01-01"  # first full year with all six ETFs trading (VNQ listed 2004-09)
END = "2026-10-01"  # exclusive; snapshot covers through 2026-09-30

TRADING_DAYS = 252
COST_BPS = 10.0  # one-way transaction cost per unit of turnover, in basis points
REBALANCE = "M"  # monthly, on the last trading day of each month
