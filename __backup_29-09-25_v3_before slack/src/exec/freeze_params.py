# src/exec/freeze_params.py
import argparse, json, sys
from pathlib import Path
import pandas as pd
import yaml

def resolve_summary(path_like: str) -> Path:
    p = Path(path_like)
    # if it's a directory, expect summary.csv inside
    if p.exists() and p.is_dir():
        candidate = p / "summary.csv"
        if not candidate.exists():
            raise SystemExit(f"No summary.csv in directory: {p}")
        return candidate

    # if literal file exists
    if p.exists() and p.is_file():
        return p

    # treat as glob (wildcards)
    root = Path.cwd()
    matches = list(root.glob(path_like))
    if not matches:
        raise SystemExit(f"No files matched: {path_like}")
    # pick newest by mtime
    matches.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return matches[0]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wf_summary", required=True,
                    help="Path to summary.csv, or directory containing it, or a glob like runs/walkforward/wf_*/summary.csv")
    ap.add_argument("--prod_yaml", default="config/production.yaml")
    args = ap.parse_args()

    summary_path = resolve_summary(args.wf_summary)
    print(f"Using walk-forward summary: {summary_path}")

    df = pd.read_csv(summary_path)
    if df.empty:
        raise SystemExit(f"No rows in {summary_path}")

    # choose best by OOS Sharpe (fallback to IS if OOS absent), tie-break lower |DD|
    metric = "oos_sharpe" if "oos_sharpe" in df.columns else "is_sharpe"
    ddcol  = "oos_maxdd"  if "oos_maxdd"  in df.columns else "is_maxdd"
    df["absdd"] = df[ddcol].abs()
    best = df.sort_values([metric, "absdd"], ascending=[False, True]).iloc[0]

    params = json.loads(best["params"]) if "params" in best and isinstance(best["params"], str) else {}

    prod_path = Path(args.prod_yaml)
    if not prod_path.exists():
        raise SystemExit(f"Missing production YAML: {prod_path}")
    prod = yaml.safe_load(prod_path.read_text(encoding="utf-8"))

    # update fields if present in params
    prod.setdefault("risk", {})
    prod.setdefault("weights", {})
    prod.setdefault("volcarry", {})

    prod["risk"]["target_ann_vol"] = float(params.get("target_vol", prod["risk"].get("target_ann_vol", 0.12)))
    prod["risk"]["vol_lookback"]   = int(params.get("vol_lookback", prod["risk"].get("vol_lookback", 20)))
    prod["risk"]["max_leverage"]   = float(params.get("max_leverage", prod["risk"].get("max_leverage", 3.0)))

    if "w_volcarry" in params:
        prod["weights"]["volcarry"] = float(params["w_volcarry"])

    if "vc_top_q" in params:     prod["volcarry"]["top_q"]    = float(params["vc_top_q"])
    if "vc_bot_q" in params:     prod["volcarry"]["bot_q"]    = float(params["vc_bot_q"])
    if "vc_lookback" in params:  prod["volcarry"]["lookback"] = int(params["vc_lookback"])

    prod_path.write_text(yaml.safe_dump(prod, sort_keys=False), encoding="utf-8")
    print("Production config updated:", prod_path)

if __name__ == "__main__":
    main()

