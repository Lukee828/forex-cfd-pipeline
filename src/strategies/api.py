from typing import Any
import pandas as pd, numpy as np

def _first(x: Any):
    # unwrap common result wrappers (e.g., StrategyResult)
    if hasattr(x, 'signals'): x = x.signals
    elif hasattr(x, 'signal'): x = x.signal
    elif hasattr(x, 'series'): x = x.series
    # normalize to pandas
    if isinstance(x, (pd.Series, pd.DataFrame)): return x
    if isinstance(x, (list, tuple, np.ndarray)): return pd.Series(x)
    return x

def generate_signals(strategy, df):
    """Try common strategy APIs: generate/signals/signal/run/__call__; unwrap wrappers."""
    for name in ("generate", "signals", "signal", "run"):
        fn = getattr(strategy, name, None)
        if callable(fn):
            return _first(fn(df))
    if callable(strategy):
        return _first(strategy(df))
    raise AttributeError(f"""{type(strategy).__name__} has no usable signal method""")

