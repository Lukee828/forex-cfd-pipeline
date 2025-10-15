import time
import json
from datetime import datetime
from typing import Optional, Dict, Any
import MetaTrader5 as mt5
import pandas as pd

TF = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
    "W1": mt5.TIMEFRAME_W1,
    "MN1": mt5.TIMEFRAME_MN1,
}


class RetryPolicy:
    def __init__(self, attempts: int = 3, sleep_sec: float = 0.4):
        self.attempts = attempts
        self.sleep_sec = sleep_sec


class MT5:
    def __init__(self, terminal_path: Optional[str] = None, retry: RetryPolicy = RetryPolicy()):
        self.terminal_path = terminal_path
        self.retry = retry

    def _init(self):
        ok = mt5.initialize(self.terminal_path) if self.terminal_path else mt5.initialize()
        if not ok:
            raise RuntimeError(f"mt5.initialize failed: {mt5.last_error()}")

    def _shutdown(self):
        mt5.shutdown()

    def _with_retry(self, fn):
        last = None
        for i in range(self.retry.attempts):
            try:
                self._init()
                try:
                    return fn()
                finally:
                    self._shutdown()
            except Exception as e:
                last = e
                if i == self.retry.attempts - 1:
                    raise
                time.sleep(self.retry.sleep_sec)
        raise last or RuntimeError("Unknown MT5 error")

    @staticmethod
    def _df_from_rates(rows) -> pd.DataFrame:
        if rows is None:
            return pd.DataFrame(
                columns=["open", "high", "low", "close", "tick_volume", "spread", "real_volume"]
            )
        df = pd.DataFrame.from_records(rows)
        if "time" in df.columns:
            df["time"] = pd.to_datetime(df["time"], unit="s")
            df = df.set_index("time")
        return df

    @staticmethod
    def parse_iso(dt: Optional[str]) -> Optional[datetime]:
        if not dt:
            return None
        from datetime import datetime as _dt

        try:
            if len(dt) == 10:
                return _dt.strptime(dt, "%Y-%m-%d")
            return _dt.fromisoformat(dt.replace("Z", ""))
        except Exception as e:
            raise ValueError(f"Bad datetime: {dt}") from e

    def tick(self, symbol: str) -> Optional[Dict[str, Any]]:
        def inner():
            mt5.symbol_select(symbol, True)
            t = mt5.symbol_info_tick(symbol)
            if t is None:
                return None
            return getattr(
                t, "_asdict", lambda: {k: getattr(t, k) for k in dir(t) if not k.startswith("_")}
            )()

        return self._with_retry(inner)

    def copy_rates_df(self, symbol: str, timeframe: str = "M5", count: int = 200) -> pd.DataFrame:
        tf = TF.get(timeframe.upper())
        if tf is None:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        def inner():
            mt5.symbol_select(symbol, True)
            from datetime import datetime as _dt

            rows = mt5.copy_rates_from(symbol, tf, _dt.now(), count)
            return self._df_from_rates(rows)

        return self._with_retry(inner)

    def copy_rates_range_df(
        self, symbol: str, timeframe: str, dt_from: str, dt_to: str
    ) -> pd.DataFrame:
        tf = TF.get(timeframe.upper())
        if tf is None:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        f = self.parse_iso(dt_from)
        t = self.parse_iso(dt_to)
        if not (f and t):
            raise ValueError("Both dt_from and dt_to required")

        def inner():
            mt5.symbol_select(symbol, True)
            rows = mt5.copy_rates_range(symbol, tf, f, t)
            return self._df_from_rates(rows)

        return self._with_retry(inner)

    def positions(self, symbol: Optional[str] = None):
        def inner():
            q = dict(symbol=symbol) if symbol else {}
            res = mt5.positions_get(**q)
            if res is None:
                return []
            return [
                getattr(
                    x,
                    "_asdict",
                    lambda: {k: getattr(x, k) for k in dir(x) if not k.startswith("_")},
                )()
                for x in res
            ]

        return self._with_retry(inner)

    def orders(self, symbol: Optional[str] = None):
        def inner():
            q = dict(symbol=symbol) if symbol else {}
            res = mt5.orders_get(**q)
            if res is None:
                return []
            return [
                getattr(
                    x,
                    "_asdict",
                    lambda: {k: getattr(x, k) for k in dir(x) if not k.startswith("_")},
                )()
                for x in res
            ]

        return self._with_retry(inner)


def _cli():
    import argparse
    import sys
    import os

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--mode", choices=["ticks", "rates", "rates_range", "positions", "orders"], required=True
    )
    ap.add_argument("--symbols", nargs="+", default=["XAUUSD", "US30", "DE40"])
    ap.add_argument("--timeframe", default="M5")
    ap.add_argument("--count", type=int, default=200)
    ap.add_argument("--from", dest="dt_from", default=None)
    ap.add_argument("--to", dest="dt_to", default=None)
    ap.add_argument("--outcsv", default=None)
    ap.add_argument("--outparquet", default=None)
    a = ap.parse_args()

    api = MT5()

    if a.mode == "ticks":
        out = {s: api.tick(s) for s in a.symbols}
        print(json.dumps(out, ensure_ascii=False))
        return
    elif a.mode == "positions":
        print(json.dumps(MT5().positions(), ensure_ascii=False))
        return
    elif a.mode == "orders":
        print(json.dumps(MT5().orders(), ensure_ascii=False))
        return
    elif a.mode == "rates":
        if len(a.symbols) != 1:
            print("ERROR: --mode rates needs one symbol", file=sys.stderr)
            sys.exit(2)
        df = api.copy_rates_df(a.symbols[0], timeframe=a.timeframe, count=a.count)
    else:  # rates_range
        if len(a.symbols) != 1:
            print("ERROR: --mode rates_range needs one symbol", file=sys.stderr)
            sys.exit(2)
        if not (a.dt_from and a.dt_to):
            print("ERROR: rates_range needs --from and --to", file=sys.stderr)
            sys.exit(2)
        df = api.copy_rates_range_df(
            a.symbols[0], timeframe=a.timeframe, dt_from=a.dt_from, dt_to=a.dt_to
        )

    if a.outparquet:
        df.to_parquet(a.outparquet, index=True)
        print("WROTE_PARQUET", os.path.abspath(a.outparquet))
        return
    if a.outcsv:
        df.to_csv(a.outcsv)
        print("WROTE_CSV", os.path.abspath(a.outcsv))
        return
    print(df.to_csv())


if __name__ == "__main__":
    _cli()
