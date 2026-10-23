"""Build the SQLite database, run every analysis query and save the results.

Outputs: results/sql/<query>.csv for each query and results/sql/rolling_vol_63d.csv.
"""

from prpa import config
from prpa.db import QUERIES, build, query

OUT = config.ROOT / "results" / "sql"


def main() -> None:
    build()
    OUT.mkdir(parents=True, exist_ok=True)
    for q in QUERIES + ["rolling_vol_63d"]:
        df = query(q)
        df.to_csv(OUT / f"{q}.csv", index=False, float_format="%.6f")
        print(f"{q}: {len(df)} rows")


if __name__ == "__main__":
    main()
