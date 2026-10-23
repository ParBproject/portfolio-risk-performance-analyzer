"""Download a frozen snapshot from Yahoo Finance (via yfinance) and write a hash manifest.

Run once with `make data`. Everything downstream reads the frozen CSVs, never the network.
"""

import hashlib
import json
from datetime import datetime, timezone

import pandas as pd

from prpa import config


def sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download() -> None:
    import yfinance as yf

    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    tickers = list(config.UNIVERSE) + [config.RISK_FREE]
    files = {}
    for t in tickers:
        df = yf.download(
            t, start=config.START, end=config.END, auto_adjust=False, progress=False, actions=False
        )
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Open", "High", "Low", "Close", "Adj Close", "Volume"]]
        df.index.name = "date"
        name = t.replace("^", "") + ".csv"
        path = config.RAW_DIR / name
        df.to_csv(path, float_format="%.8f")
        files[name] = {
            "ticker": t,
            "rows": len(df),
            "first": str(df.index[0].date()),
            "last": str(df.index[-1].date()),
            "sha256": sha256(path),
        }
    manifest = {
        "source": "Yahoo Finance via yfinance " + yf.__version__,
        "adjustment": "auto_adjust=False; 'Adj Close' is split- and dividend-adjusted",
        "downloaded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "start": config.START,
        "end_exclusive": config.END,
        "files": files,
    }
    config.MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")


def verify() -> None:
    """Fail loudly if any frozen file differs from the manifest."""
    m = json.loads(config.MANIFEST.read_text())
    for name, meta in m["files"].items():
        got = sha256(config.RAW_DIR / name)
        if got != meta["sha256"]:
            raise ValueError(f"{name}: hash mismatch {got} != {meta['sha256']}")


if __name__ == "__main__":
    download()
    verify()
    print("snapshot written and verified")
