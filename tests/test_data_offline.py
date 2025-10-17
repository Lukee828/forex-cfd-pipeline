from __future__ import annotations
import os
from src.data.dukascopy import BarSpec, get_bars
def test_offline_bars_smoke():
    os.environ["DUKASCOPY_OFFLINE"]="1"
    df = get_bars(BarSpec("EURUSD","H1","2024-01-01","2024-01-10"))
    assert not df.empty and {"open","high","low","close","volume"} <= set(df.columns)
