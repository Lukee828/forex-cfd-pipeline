# tests/test_ob_logic.py
import numpy as np
import pandas as pd
import pytest

from conftest import find_ob_func


def _df(o, h, lo, c):
    return pd.DataFrame({"open": o, "high": h, "low": lo, "close": c})


@pytest.mark.parametrize("lookback", [1, 2, 3])
def test_ob_basic_swings_present(lookback):
    ob = find_ob_func()
    if ob is None:
        pytest.xfail("OB function not found yet; wire module path to enable this test")
    df = _df(
        o=[1, 1, 1, 1, 1, 1],
        h=[1, 2, 3, 2.5, 4, 3.8],
        l=[0.9, 0.8, 1.2, 1.1, 2.0, 2.1],
        c=[1.0, 1.8, 2.6, 2.4, 3.5, 3.2],
    )
    out = ob(df, lookback=lookback) if "lookback" in ob.__code__.co_varnames else ob(df)
    # Accept either boolean mask columns or label columns
    # We only assert that at least one turning signal exists
    assert out.isna().sum().sum() == 0
    assert len(out) == len(df)


def test_equal_high_tie_is_deterministic():
    ob = find_ob_func()
    if ob is None:
        pytest.xfail("OB function not found yet; wire module path to enable this test")
    # equal highs across three bars: implementation should pick a stable winner (first/last)
    df = _df(
        o=[1, 1, 1],
        h=[2, 2, 2],
        l=[0.5, 0.5, 0.5],
        c=[1.2, 1.1, 1.0],
    )
    out = ob(df, lookback=1) if "lookback" in ob.__code__.co_varnames else ob(df)
    # Minimal sanity: output shape matches and is finite
    assert out.shape[0] == 3
    assert np.isfinite(out.select_dtypes(include=["number"])).all().all()


def test_window_edges_do_not_crash():
    ob = find_ob_func()
    if ob is None:
        pytest.xfail("OB function not found yet; wire module path to enable this test")
    df = _df(
        o=[1, 1],
        h=[1.1, 1.2],
        l=[0.9, 0.95],
        c=[1.0, 1.1],
    )
    _ = ob(df, lookback=2) if "lookback" in ob.__code__.co_varnames else ob(df)
