from __future__ import annotations
from pathlib import Path
import argparse
import pandas as pd
from feature.feature_store import FeatureStore  # repo code under ./src


def build_toy_prices(n: int = 10) -> pd.DataFrame:
    idx = pd.date_range("2021-01-01", periods=n, freq="D")
    return pd.DataFrame({"close": range(n)}, index=idx)


def main() -> None:
    ap = argparse.ArgumentParser(description="FeatureStore demo (roundtrip prices + provenance)")
    ap.add_argument("--db", type=Path, default=Path("runs") / "fs_demo" / "fs.db")
    ap.add_argument("--symbol", default="EURUSD")
    ap.add_argument("--rows", type=int, default=10)
    args = ap.parse_args()

    args.db.parent.mkdir(parents=True, exist_ok=True)

    store = FeatureStore(args.db)
    store.init()

    df = build_toy_prices(args.rows)
    written = store.upsert_prices(args.symbol, df)
    out = store.get_prices(args.symbol)
    prov_id = store.record_provenance(
        args.symbol, kind="prices", source="demo:use_feature_store.py", version="v1"
    )

    print("== FeatureStore Demo ==")
    print(f"DB:         {args.db}")
    print(f"Symbol:     {args.symbol}")
    print(f"Written:    {written} rows")
    print(f"Read back:  {len(out)} rows")
    print(f"Last close: {out['close'].iloc[-1] if not out.empty else 'n/a'}")
    print(f"Provenance: id={prov_id}")


if __name__ == "__main__":
    main()
