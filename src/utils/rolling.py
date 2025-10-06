from __future__ import annotations
import os
import numpy as np

try:
    import numba  # type: ignore
except Exception:  # pragma: no cover
    numba = None  # fall back when unavailable


def _roll_mean_numpy(x: np.ndarray, window: int) -> np.ndarray:
    if window <= 0:
        raise ValueError("window must be >= 1")
    x = np.asarray(x, dtype=float)
    out = np.empty_like(x, dtype=float)
    out[:] = np.nan
    if len(x) < window:
        return out
    c = np.cumsum(x, dtype=float)
    out[window - 1 :] = (
        c[window - 1 :] - np.concatenate(([0.0], c[:-window]))
    ) / window
    return out


if numba is not None:

    @numba.njit(cache=True, fastmath=False)
    def _roll_mean_numba(x: np.ndarray, window: int) -> np.ndarray:  # pragma: no cover
        n = x.shape[0]
        out = np.empty(n, dtype=np.float64)
        for i in range(n):
            out[i] = np.nan
        if window <= 0 or n < window:
            return out
        s = 0.0
        for i in range(window):
            s += x[i]
        out[window - 1] = s / window
        for i in range(window, n):
            s += x[i] - x[i - window]
            out[i] = s / window
        return out

else:
    _roll_mean_numba = None


def roll_mean(x: np.ndarray, window: int) -> np.ndarray:
    impl = (os.getenv("ROLL_IMPL") or "").lower()
    if impl == "numba" and _roll_mean_numba is not None:
        return _roll_mean_numba(np.asarray(x, dtype=float), window)
    return _roll_mean_numpy(x, window)
