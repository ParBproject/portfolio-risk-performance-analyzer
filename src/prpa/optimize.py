"""Long-only, fully invested minimum-variance weights, estimated from past data only."""

from itertools import combinations

import numpy as np
import pandas as pd

from prpa.portfolio import rebalance_dates

WINDOW = 252  # trailing 1 year of daily returns (standard choice, not tuned)


def min_variance(cov: np.ndarray) -> np.ndarray:
    """Exact solution of min w'Σw s.t. sum(w)=1, w>=0.

    The long-only optimum equals the unconstrained optimum (w ∝ Σ_S⁻¹1) on its own support S.
    With few assets we can try every support and keep the feasible one with lowest variance.
    6 assets -> 63 subsets, so this is exact, fast and needs no solver dependency.
    """
    n = cov.shape[0]
    best, best_var = None, np.inf
    for k in range(1, n + 1):
        for S in combinations(range(n), k):
            sub = cov[np.ix_(S, S)]
            try:
                x = np.linalg.solve(sub, np.ones(k))
            except np.linalg.LinAlgError:
                continue
            w_s = x / x.sum()
            if (w_s < -1e-12).any():
                continue
            w = np.zeros(n)
            w[list(S)] = np.clip(w_s, 0, None)
            w /= w.sum()
            v = w @ cov @ w
            if v < best_var - 1e-18:
                best, best_var = w, v
    return best


def rolling_min_variance(
    returns: pd.DataFrame, window: int = WINDOW, freq: str = "M"
) -> pd.DataFrame:
    """Target weights at each month-end close, using only the `window` returns up to that day.

    Rows are rebalance dates; the weights are first applied to the NEXT day's returns.
    Month-ends with fewer than `window` past returns are skipped.
    """
    rows = {}
    pos = {d: i for i, d in enumerate(returns.index)}
    for d in rebalance_dates(returns.index, freq):
        i = pos[d]
        if i + 1 < window:
            continue
        hist = returns.iloc[i + 1 - window : i + 1]
        rows[d] = min_variance(hist.cov().values)
    return pd.DataFrame.from_dict(rows, orient="index", columns=returns.columns)
