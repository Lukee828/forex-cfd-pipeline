from __future__ import annotations
import pandas as pd


def overbalance(pivots: pd.DataFrame, lookback: int = 5) -> pd.DataFrame:
    """
    Flag an "overbalance" when the *current* swing magnitude exceeds the rolling
    max of the prior `lookback` swings.

    Input `pivots` must contain:
      - "timestamp" (datetime-like)
      - "close"     (float)
      - "pivot"     (bool) True at swing turning points

    Returns a DataFrame (same length) with a boolean column `overbalanced`
    that is True only at pivot rows where the condition is met.
    """
    if not {"timestamp", "close", "pivot"} <= set(pivots.columns):
        raise ValueError("pivots must include columns: timestamp, close, pivot")

    pivots = pivots.reset_index(drop=True).copy()
    # Indices of actual pivot points
    pidx = pivots.index[pivots["pivot"].astype(bool)].to_list()

    over = pd.Series(False, index=pivots.index)

    if len(pidx) < 2:
        return pd.DataFrame({"overbalanced": over})

    # Swing magnitudes between consecutive pivot points
    # swing i is between pidx[i-1] -> pidx[i], magnitude = abs(diff close)
    swing_mags = []
    for i in range(1, len(pidx)):
        a, b = pidx[i - 1], pidx[i]
        swing_mags.append(abs(pivots.loc[b, "close"] - pivots.loc[a, "close"]))

    # For each swing (starting at index 1 of pivot list), compare vs rolling max of prior swings
    for i in range(1, len(pidx)):
        curr_mag = swing_mags[i - 1]
        start = max(0, i - lookback)
        prior = swing_mags[start:i]  # swings before the current one
        if len(prior) > 0 and curr_mag > max(prior):
            over.loc[pidx[i]] = True  # mark on the *ending* pivot of that swing

    return pd.DataFrame({"overbalanced": over})
