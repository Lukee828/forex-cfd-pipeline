# sweep_robustness.py — IS/OOS-aware robustness grid with safe writes

import argparse, itertools, subprocess, sys, math, time, os
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np

# ---------- shared root helpers ----------
from pathlib import Path as _P
import os as _os

PRESET_ROOT = r"C:\Users\speed\Desktop\Forex CFD's system"

def detect_project_root(preset: str = PRESET_ROOT) -> _P:
    env = _os.environ.get("PROJECT_ROOT")
    if env and _P(env).exists():
        return _P(env)
    if preset and _P(preset).exists():
        return _P(preset)
    return _P.cwd()

def default_paths():
    ROOT = detect_project_root()
    d1 = ROOT / "data" / "prices_1d"
    dH = ROOT / "data" / "prices_1h"
    folder = d1 if d1.exists() else (dH if dH.exists() else d1)
    cfg = ROOT / "config" / "baseline.yaml"
    costs = ROOT / "data" / "costs_per_symbol.csv"
    return ROOT, folder, cfg, costs

# ---------- utils ----------
def ann_metrics(equity_csv: Path):
    eq = pd.read_csv(equity_csv, parse_dates=['ts']).set_index('ts')
    port = eq['portfolio_equity'].dropna()
    if len(port) < 3:
        return dict(cagr=np.nan, vol=np.nan, sharpe=np.nan, maxdd=np.nan, mar=np.nan)
    ret = port.pct_change().dropna()
    years = (port.index[-1] - port.index[0]).days/365.25 if len(port)>1 else np.nan
    cagr = port.iloc[-1]**(1/years) - 1 if (isinstance(years,float) and years>0) else np.nan
    vol = ret.std()*math.sqrt(252) if len(ret)>2 else np.nan
    dd = (port/port.cummax()-1.0).min() if len(port)>1 else np.nan
    sharpe = (cagr-0.0)/vol if (isinstance(vol,float) and vol>0) else np.nan
    mar = (cagr/abs(dd)) if (isinstance(cagr,float) and isinstance(dd,float) and dd<0) else np.nan
    return dict(cagr=cagr, vol=vol, sharpe=sharpe, maxdd=dd, mar=mar)

def run_cmd(cmd, cwd=None):
    cp = subprocess.run(cmd, text=True, capture_output=True, cwd=cwd)
    if cp.returncode != 0:
        print("---- STDOUT ----\n", cp.stdout)
        print("---- STDERR ----\n", cp.stderr)
        raise SystemExit(f"Command failed: {' '.join(cmd)}")
    return cp.stdout

def safe_to_csv(df: pd.DataFrame, path: Path, retries=3, delay=0.5) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(retries):
        try:
            tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
            df.to_csv(tmp, index=False)
            try:
                os.replace(tmp, path)
                return path
            except PermissionError:
                # fall back to timestamped file if locked
                alt = path.with_name(f"{path.stem}_{int(time.time())}{path.suffix}")
                os.replace(tmp, alt)
                return alt
        except PermissionError:
            time.sleep(delay)
    raise PermissionError(f"Could not write {path} (is it open in Excel?)")

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", default=None)
    ap.add_argument("--folder", default=None)
    ap.add_argument("--costs_csv", default=None)

    # NEW: IS/OOS time windows passed to backtester
    ap.add_argument("--start", default=None, help="YYYY-MM-DD (UTC)")
    ap.add_argument("--end",   default=None, help="YYYY-MM-DD (UTC)")

    # grids
    ap.add_argument("--w_volcarry_grid", default="0.0,0.3,0.5")
    ap.add_argument("--volcarry_topq_grid", default="0.25,0.35,0.45")
    ap.add_argument("--volcarry_botq_grid", default="0.25,0.35,0.45")
    ap.add_argument("--volcarry_lookback_grid", default="42,63,84")
    ap.add_argument("--target_vol_grid", default="0.10,0.12,0.15")
    ap.add_argument("--vol_lookback_grid", default="15,20,30")
    ap.add_argument("--max_lev_grid", default="2.0,3.0")

    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out_root", default=None)
    args = ap.parse_args()

    ROOT, DEF_FOLDER, DEF_CFG, DEF_COSTS = default_paths()
    folder = Path(args.folder) if args.folder else DEF_FOLDER
    cfg = Path(args.cfg) if args.cfg else DEF_CFG
    costs = Path(args.costs_csv) if args.costs_csv else DEF_COSTS
    if not folder.exists():
        raise SystemExit(f"Data folder not found: {folder}")

    out_root = Path(args.out_root) if args.out_root else (ROOT/"runs"/f"robustness_{datetime.now().strftime('%Y%m%d_%H%M')}")
    out_root.mkdir(parents=True, exist_ok=True)

    def parse_list(s): return [x.strip() for x in s.split(",") if x.strip()]
    def parse_float(s): return [float(x) for x in parse_list(s)]
    def parse_int(s): return [int(x) for x in parse_list(s)]

    wv   = parse_float(args.w_volcarry_grid)
    vct  = parse_float(args.volcarry_topq_grid)
    vcb  = parse_float(args.volcarry_botq_grid)
    vclb = parse_int(args.volcarry_lookback_grid)
    tv   = parse_float(args.target_vol_grid)
    vlb  = parse_int(args.vol_lookback_grid)
    ml   = parse_float(args.max_lev_grid)

    combos = list(itertools.product(wv, vct, vcb, vclb, tv, vlb, ml))
    if args.limit and args.limit > 0:
        combos = combos[:args.limit]

    rows = []
    for i, (wv_, vct_, vcb_, vclb_, tv_, vlb_, ml_) in enumerate(combos, 1):
        run_dir = out_root / f"run_{i:04d}"
        run_dir.mkdir(parents=True, exist_ok=True)
        prefix = f"sweep_run_{i:04d}"

        cmd = [
            sys.executable, "-m", "src.exec.backtest_pnl_demo",
            "--cfg", str(cfg),
            "--folder", str(folder),
            "--costs_csv", str(costs),
            "--target_ann_vol", str(tv_),
            "--vol_lookback", str(vlb_),
            "--max_leverage", str(ml_),
            "--w_volcarry", str(wv_),
            "--volcarry_top_q", str(vct_),
            "--volcarry_bot_q", str(vcb_),
            "--volcarry_lookback", str(vclb_),
            "--out_prefix", prefix,  # NEW: isolate outputs per run
        ]
        if args.start:
            cmd += ["--start", args.start]
        if args.end:
            cmd += ["--end", args.end]

        _ = run_cmd(cmd, cwd=str(ROOT))

        # collect metrics from per-run equity
        eq_src = ROOT / "data" / f"{prefix}_equity.csv"
        if not eq_src.exists():
            # fallback to default name if out_prefix not supported in backtester
            eq_src = ROOT / "data" / "pnl_demo_equity.csv"
        if eq_src.exists():
            (run_dir / "equity.csv").write_bytes(eq_src.read_bytes())
            m = ann_metrics(run_dir / "equity.csv")
            row = dict(
                run=i, loo="-", lookbacks="(63,126,252)",
                w_tsmom=1.0, w_xsec=0.8, w_mr=0.6,
                w_volcarry=wv_, vc_top_q=vct_, vc_bot_q=vcb_, vc_lookback=vclb_,
                target_vol=tv_, vol_lookback=vlb_, max_leverage=ml_,
                **m
            )
            rows.append(row)

        # write/update summary safely each iteration
        if rows:
            safe_to_csv(pd.DataFrame(rows), out_root / "summary.csv")

    print("Saved robustness results to", out_root.resolve())

if __name__ == "__main__":
    main()
