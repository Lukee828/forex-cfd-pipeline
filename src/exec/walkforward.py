# src/exec/walkforward.py
import argparse
import subprocess
import sys
import json
import math
import re
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

ROOT = Path(r"C:\Users\speed\Desktop\Forex CFD's system")  # adjust if needed


def run(cmd, cwd=ROOT):
    cp = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    if cp.returncode != 0:
        print("---- STDOUT ----\n", cp.stdout)
        print("---- STDERR ----\n", cp.stderr)
        raise SystemExit(f"Command failed: {' '.join(cmd)}")
    return cp.stdout


def pick_best_is(summary_csv: Path):
    df = pd.read_csv(summary_csv)
    if df.empty:
        raise SystemExit(f"No rows in {summary_csv}")
    df["absdd"] = df["maxdd"].abs()
    df = df.sort_values(
        ["sharpe", "absdd", "vol", "mar"], ascending=[False, True, True, False]
    )
    return df.iloc[0].to_dict()


def metrics_from_equity(equity_csv: Path):
    eq = pd.read_csv(equity_csv, parse_dates=["ts"]).set_index("ts")
    port = eq["portfolio_equity"].dropna()
    if len(port) < 3:
        return dict(cagr=np.nan, vol=np.nan, sharpe=np.nan, maxdd=np.nan, mar=np.nan)
    ret = port.pct_change().dropna()
    years = (port.index[-1] - port.index[0]).days / 365.25
    cagr = port.iloc[-1] ** (1 / years) - 1 if years > 0 else np.nan
    vol = ret.std() * math.sqrt(252)
    dd = (port / port.cummax() - 1).min()
    sharpe = cagr / vol if vol > 0 else np.nan
    mar = cagr / abs(dd) if dd < 0 else np.nan
    return dict(cagr=cagr, vol=vol, sharpe=sharpe, maxdd=dd, mar=mar)


def _json_loads_tolerant(s: str):
    # try straight
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    # remove potential UTF-8 BOM
    try:
        s2 = s.encode("utf-8").decode("utf-8-sig")
        return json.loads(s2)
    except Exception:
        pass
    # naive single->double quote swap (PowerShell)
    try:
        s3 = re.sub(r"'", '"', s)
        return json.loads(s3)
    except Exception as e:
        raise SystemExit(
            f"Failed to parse JSON for --folds/--folds_file:\n{s}\nError: {e}"
        )


def main():
    ap = argparse.ArgumentParser()

    # Mutually exclusive: either --folds (inline JSON or @file) OR --folds_file path
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument(
        "--folds",
        help="JSON list, or prefix with @file, e.g. --folds @runs\\wf_folds.json",
    )
    grp.add_argument("--folds_file", help="Path to JSON file with folds")

    # sweep grids (IS)
    ap.add_argument("--w_volcarry_grid", default="0.0,0.3")
    ap.add_argument("--volcarry_topq_grid", default="0.25,0.45")
    ap.add_argument("--volcarry_botq_grid", default="0.25,0.45")
    ap.add_argument("--volcarry_lookback_grid", default="42,84")
    ap.add_argument("--target_vol_grid", default="0.10,0.15")
    ap.add_argument("--vol_lookback_grid", default="15,30")
    ap.add_argument("--max_lev_grid", default="2.0,3.0")
    ap.add_argument("--limit", type=int, default=16)

    ap.add_argument("--folder", default=str(ROOT / "data" / "prices_1d"))
    ap.add_argument("--costs_csv", default=str(ROOT / "data" / "costs_per_symbol.csv"))
    ap.add_argument("--out_root", default=str(ROOT / "runs" / "walkforward"))
    ap.add_argument("--run_id", default=datetime.now().strftime("wf_%Y%m%d_%H%M"))
    ap.add_argument(
        "--autofreeze",
        dest="autofreeze",
        action="store_true",
        default=True,
        help="After finishing, write best params into production.yaml (default: on)",
    )
    ap.add_argument(
        "--no-autofreeze",
        dest="autofreeze",
        action="store_false",
        help="Disable auto-write to production.yaml",
    )
    ap.add_argument(
        "--prod_yaml",
        default=str(ROOT / "config" / "production.yaml"),
        help="Path to production YAML to update",
    )

    args = ap.parse_args()

    # Resolve folds
    if args.folds_file:
        s = Path(args.folds_file).read_text(encoding="utf-8-sig")
        folds = _json_loads_tolerant(s)
    else:
        s = args.folds.strip()
        if s.startswith("@"):  # support curl-like @file
            p = Path(s[1:])
            s = p.read_text(encoding="utf-8-sig")
        folds = _json_loads_tolerant(s)

    out_root = Path(args.out_root) / args.run_id
    out_root.mkdir(parents=True, exist_ok=True)

    results = []
    for k, f in enumerate(folds, 1):
        tag = f"fold_{k:02d}"
        is_dir = out_root / (tag + "_IS")
        oos_dir = out_root / (tag + "_OOS")
        is_dir.mkdir(parents=True, exist_ok=True)
        oos_dir.mkdir(parents=True, exist_ok=True)

        # 1) IS sweep
        cmd_is = [
            sys.executable,
            "-m",
            "src.exec.sweep_robustness",
            "--folder",
            args.folder,
            "--costs_csv",
            args.costs_csv,
            "--start",
            f["is_start"],
            "--end",
            f["is_end"],
            "--w_volcarry_grid",
            args.w_volcarry_grid,
            "--volcarry_topq_grid",
            args.volcarry_topq_grid,
            "--volcarry_botq_grid",
            args.volcarry_botq_grid,
            "--volcarry_lookback_grid",
            args.volcarry_lookback_grid,
            "--target_vol_grid",
            args.target_vol_grid,
            "--vol_lookback_grid",
            args.vol_lookback_grid,
            "--max_lev_grid",
            args.max_lev_grid,
            "--limit",
            str(args.limit),
            "--out_root",
            str(is_dir),
        ]
        print("RUN IS:", " ".join(cmd_is))
        run(cmd_is)
        is_summary = is_dir / "summary.csv"
        best = pick_best_is(is_summary)

        # 2) OOS backtest using the best IS params
        prefix = f"{tag}_BEST"
        cmd_oos = [
            sys.executable,
            "-m",
            "src.exec.backtest_pnl_demo",
            "--folder",
            args.folder,
            "--costs_csv",
            args.costs_csv,
            "--start",
            f["oos_start"],
            "--end",
            f["oos_end"],
            "--target_ann_vol",
            str(best.get("target_vol", 0.12)),
            "--vol_lookback",
            str(int(best.get("vol_lookback", 20))),
            "--max_leverage",
            str(best.get("max_leverage", 3.0)),
            "--w_tsmom",
            "1.0",
            "--w_xsec",
            "0.8",
            "--w_mr",
            "0.6",
            "--w_volcarry",
            str(best.get("w_volcarry", 0.0)),
            "--volcarry_top_q",
            str(best.get("vc_top_q", 0.35)),
            "--volcarry_bot_q",
            str(best.get("vc_bot_q", 0.35)),
            "--volcarry_lookback",
            str(int(best.get("vc_lookback", 63))),
            "--out_prefix",
            prefix,
        ]
        print("RUN OOS:", " ".join(cmd_oos))
        run(cmd_oos)

        # metrics
        is_metrics = pick_best_is(is_summary)
        oos_eq = ROOT / "data" / f"{prefix}_equity.csv"
        oos_metrics = metrics_from_equity(oos_eq)
        row = {
            "fold": k,
            "is_start": f["is_start"],
            "is_end": f["is_end"],
            "oos_start": f["oos_start"],
            "oos_end": f["oos_end"],
            "is_sharpe": is_metrics.get("sharpe"),
            "is_maxdd": is_metrics.get("maxdd"),
            "oos_sharpe": oos_metrics.get("sharpe"),
            "oos_maxdd": oos_metrics.get("maxdd"),
            "params": json.dumps(
                {
                    "target_vol": is_metrics.get("target_vol"),
                    "vol_lookback": is_metrics.get("vol_lookback"),
                    "max_leverage": is_metrics.get("max_leverage"),
                    "w_tsmom": 1.0,
                    "w_xsec": 0.8,
                    "w_mr": 0.6,
                    "w_volcarry": is_metrics.get("w_volcarry"),
                    "vc_top_q": is_metrics.get("vc_top_q"),
                    "vc_bot_q": is_metrics.get("vc_bot_q"),
                    "vc_lookback": is_metrics.get("vc_lookback"),
                }
            ),
        }
        results.append(row)

    out_csv = out_root / "summary.csv"
    pd.DataFrame(results).to_csv(out_csv, index=False)
    print("Walk-forward summary saved to", out_csv.resolve())

    # ----- Auto-freeze best params into production.yaml -----
    if args.autofreeze:
        freeze_cmd = [
            sys.executable,
            "-m",
            "src.exec.freeze_params",
            "--wf_summary",
            str(out_csv),
            "--prod_yaml",
            args.prod_yaml,
        ]
        print("AUTO-FREEZE:", " ".join(freeze_cmd))
        run(freeze_cmd)  # will print "Production config updated: ..."


if __name__ == "__main__":
    main()
