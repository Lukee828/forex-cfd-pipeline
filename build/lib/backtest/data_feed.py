import os
import pandas as pd


class ParquetDataFeed:
    def __init__(self, root: str, symbols):
        self.root = root
        self.symbols = list(symbols)

    def get_closes(self, limit=None):
        frames = []
        for sym in self.symbols:
            p = os.path.join(self.root, f"{sym}.parquet")
            df = pd.read_parquet(p)
            # accept any reasonable casing; select the first matching close-like column
            cols = {c.lower(): c for c in df.columns}
            close_col = None
            for key in ("close", "adj close", "adj_close"):
                if key in cols:
                    close_col = cols[key]
                    break
            if close_col is None:
                raise KeyError(f"{sym}: no Close column in {p} (have {list(df.columns)})")
            cl = df[close_col].astype(float).rename(sym)
            frames.append(cl)

        closes = pd.concat(frames, axis=1).sort_index()
        closes = closes.replace([float("inf"), float("-inf")], pd.NA).ffill().bfill()

        if limit is not None:
            closes = closes.iloc[: int(limit)]

        return closes
