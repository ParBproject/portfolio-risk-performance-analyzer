"""Long-only, fully invested minimum-variance weights, estimated from past data only."""

from itertools import combinations

import numpy as np
import pandas as pd

from prpa.portfolio import rebalance_dates

WINDOW = 252  # trailing year of daily returns


def _min_var_sum_to_one(sub: np.ndarray) -> np.ndarray | None:
    """Minimum-variance weights that sum to 1. Short sales are allowed.

    For a singular block the inverse formula does not apply (a riskless asset, or
    two assets that hedge each other). Write w = w0 + Z c with 1'Z = 0 and
    minimize the quadratic in c. Returns None if that problem has no finite solution.
    """
    k = sub.shape[0]
    if k == 1:
        return np.ones(1)
    w0 = np.zeros(k)
    w0[0] = 1.0
    z = np.vstack([-np.ones((1, k - 1)), np.eye(k - 1)])
    gram = z.T @ sub @ z
    linear = z.T @ sub @ w0
    try:
        coeff = np.linalg.solve(gram, -linear)
    except np.linalg.LinAlgError:
        coeff, _, _, _ = np.linalg.lstsq(gram, -linear, rcond=None)
    if not np.all(np.isfinite(coeff)):
        return None
    weights = w0 + z @ coeff
    total = float(weights.sum())
    if not np.all(np.isfinite(weights)) or not total > 1e-12:
        return None
    return weights / total


def min_variance(cov: np.ndarray) -> np.ndarray:
    """Long-only minimum variance: min w'Σw s.t. sum(w)=1, w>=0.

    On a support S the candidate sums to 1 and is kept only if every weight is
    non-negative. Invertible blocks use w ∝ Σ_S⁻¹ 1. A singular block is minimized
    on the sum-to-one plane instead of being dropped. Six assets means 63 subsets,
    so trying each one is an exact solve.
    """
    n = cov.shape[0]
    best, best_var = None, np.inf
    for k in range(1, n + 1):
        for S in combinations(range(n), k):
            sub = cov[np.ix_(S, S)]
            try:
                x = np.linalg.solve(sub, np.ones(k))
            except np.linalg.LinAlgError:
                w_s = _min_var_sum_to_one(sub)
                if w_s is None:
                    continue
            else:
                total = float(x.sum())
                scale = float(np.max(np.abs(x)))
                # x = Σ^{-1} 1 is un-normalized. Reject a non-finite sum, or one
                # that is ~0 next to ||x||: dividing by it yields Inf/NaN, and
                # `w < -1e-12` does not see NaN. An absolute 1e-12 cut would drop
                # a real solution when variances are large (the sum scales as 1/σ²).
                if (
                    not np.all(np.isfinite(x))
                    or not np.isfinite(total)
                    or not abs(total) > 1e-12 * scale
                ):
                    continue
                w_s = x / total
            if not np.all(np.isfinite(w_s)) or (w_s < -1e-12).any():
                continue
            w = np.zeros(n)
            w[list(S)] = np.clip(w_s, 0, None)
            total_w = float(w.sum())
            if not np.isfinite(total_w) or total_w <= 0:
                continue
            w /= total_w
            v = float(w @ cov @ w)
            if np.isfinite(v) and v < best_var - 1e-18:
                best, best_var = w, v
    if best is None:
        raise ValueError("no feasible long-only portfolio")
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
