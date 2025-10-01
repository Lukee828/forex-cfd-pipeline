from typing import Dict, List
import pandas as pd
from ..events import MarketEvent, SignalEvent
from ..strategy.base import Strategy


class MovingAverageCross(Strategy):
    def __init__(self, short: int = 20, long: int = 50):
        if short >= long:
            raise ValueError("short < long required")
        self.short = short
        self.long = long
        self.hist: Dict[str, pd.DataFrame] = {}  # symbol -> df with 'Close'

    def on_market(self, ev: MarketEvent) -> List[SignalEvent]:
        out: List[SignalEvent] = []
        ts = ev.ts
        for sym, bar in ev.ohlcv_by_sym.items():
            df = self.hist.setdefault(sym, pd.DataFrame(columns=["Close"]))
            df.loc[ts, "Close"] = bar["Close"]
            if len(df) >= self.long:
                s_ma = df["Close"].rolling(self.short).mean().iloc[-1]
                l_ma = df["Close"].rolling(self.long).mean().iloc[-1]
                if pd.notna(s_ma) and pd.notna(l_ma):
                    if s_ma > l_ma:
                        out.append(
                            SignalEvent(
                                ts=ts, symbol=sym, direction="LONG", strength=1.0
                            )
                        )
                    elif s_ma < l_ma:
                        out.append(
                            SignalEvent(
                                ts=ts, symbol=sym, direction="SHORT", strength=1.0
                            )
                        )
                    # else equal -> no signal
        return out
