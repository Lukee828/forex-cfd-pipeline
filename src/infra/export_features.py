# src/infra/export_features.py
import os
import pathlib

def _map_tf(tf: str) -> str:
    tl = (tf or "H1").lower()
    return {"h1":"1h","d1":"1d","m1":"1m","m5":"5m"}.get(tl, tl)

def _choose_backend():
    backend = os.getenv("EXPORTER_BACKEND", "dukascopy")
    if backend == "legacy":
        from src.data.dukascopy_downloader import save_symbol as save_fn
    else:
        from src.infra.dukascopy_downloader import save_symbol as save_fn
    return save_fn

def main():
    out_dir = pathlib.Path("artifacts/exports")
    out_dir.mkdir(parents=True, exist_ok=True)

    pairs  = os.getenv("PAIRS", "EURUSD,GBPUSD")
    tf     = _map_tf(os.getenv("TF", "H1"))
    start  = os.getenv("START", "2024-01-01")
    end    = os.getenv("END",   "2024-01-10")

    save_fn = _choose_backend()
    wrote_any = False
    for sym in [s.strip() for s in pairs.split(",") if s.strip()]:
        try:
            path = save_fn(sym, start, end, tf, str(out_dir))
            print(f"wrote: {path}")
            wrote_any = True
        except Exception as e:
            print(f"[warn] {sym}: {e}")

    # (Artifacts fallback CSV is handled in workflow shell/PS step)
    if not wrote_any:
        print("No files written by exporter (see workflow fallback step).")

if __name__ == "__main__":
    main()
