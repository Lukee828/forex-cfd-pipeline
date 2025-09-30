# src/exec/daily_run.py
# ------------------------------------------------------------
# Daily pipeline:
#   1) Backtest (to get up-to-date signals)
#   2) Write/confirm positions.csv
#   3) Make orders.csv (with sanity checks)
#   4) (Optional) Publish to MT5 (dry_run configurable)
# Includes: YAML loader with ${ENV_VAR} expansion.
# ------------------------------------------------------------

import argparse
import os
import sys
import subprocess as sp
from pathlib import Path
import shutil
import pandas as pd
from datetime import timedelta
# --- add at top of daily_run.py, with other imports ---
import warnings

# Silence harmless tz→Period warning from pandas
warnings.filterwarnings(
    "ignore",
    message="Converting to PeriodArray/Index representation will drop timezone information",
    category=UserWarning,
)

# --- config loader with ${ENV} expansion
try:
    from utils.config_loader import load_yaml_with_env
except Exception:
    # minimal fallback if utils/config_loader.py not present
    import yaml
    def load_yaml_with_env(path):
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

ROOT = Path(__file__).resolve().parents[2]  # project root .../Forex CFD's system
DATA = ROOT / "data"
SIGNALS = ROOT / "signals"
REPORTS = ROOT / "reports"
LOGS = ROOT / "logs"

def _ts_utc_now():
    """Safe UTC timestamp (tz-aware) without tz_localize mistakes."""
    return pd.Timestamp.now(tz="UTC")

def _is_weekend(ts_utc: pd.Timestamp) -> bool:
    return ts_utc.weekday() >= 5

def _ensure_dirs():
    for p in (DATA, SIGNALS, REPORTS, LOGS):
        p.mkdir(parents=True, exist_ok=True)

def _pp(cmd_list):
    return " ".join([str(x) for x in cmd_list])

def run(cmd_list, check=True):
    print("RUN:", _pp(cmd_list))
    cp = sp.run(cmd_list, capture_output=True, text=True)
    if cp.stdout:
        print(cp.stdout.strip())
    if cp.stderr:
        print(cp.stderr.strip(), file=sys.stderr)
    if check and cp.returncode != 0:
        raise sp.CalledProcessError(cp.returncode, cmd_list, cp.stdout, cp.stderr)
    return cp

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out_prefix", default=None)
    ap.add_argument("--mt5_verify_ticks", action="store_true", help="(compat flag) no-op here; kept for CLI parity")
    ap.add_argument("--mt5_verify_positions", action="store_true", help="(compat flag) no-op here; kept for CLI parity")
    args = ap.parse_args()

    _ensure_dirs()

    # --- Load config (with ${ENV} expansion)
    cfg = load_yaml_with_env(args.config)
    
    # --- MT5 credential fallback & safety ---
    exec_cfg = cfg.get("execution", {}) or {}
    mt5_cfg  = (exec_cfg.get("mt5") or {})
    # Prefer env vars, fall back to YAML, finally None
    mt5_login = os.getenv("MT5_LOGIN")    or mt5_cfg.get("login")
    mt5_pass  = os.getenv("MT5_PASSWORD") or mt5_cfg.get("password")
    mt5_srv   = os.getenv("MT5_SERVER")   or mt5_cfg.get("server")

    # Keep the resolved values in cfg so downstream uses the same source of truth
    mt5_cfg["login"]    = mt5_login
    mt5_cfg["password"] = mt5_pass
    mt5_cfg["server"]   = mt5_srv
    exec_cfg["mt5"]     = mt5_cfg
    cfg["execution"]    = exec_cfg

    # If execution enabled but any MT5 secret missing -> force dry_run (safe)
    if exec_cfg.get("enabled", False) and exec_cfg.get("broker") == "mt5":
        missing = [k for k,v in {"login": mt5_login, "password": mt5_pass, "server": mt5_srv}.items() if not v]
        if missing:
            print(f"WARN: MT5 credentials missing ({', '.join(missing)}). Forcing dry_run=True.")
            exec_cfg["dry_run"] = True

    # --- Resolve paths & settings
    uni = cfg.get("universe", {})
    out_cfg = cfg.get("output", {})
    orders_cfg = cfg.get("orders", {})
    exec_cfg = cfg.get("execution", {})
    mt5_cfg = (exec_cfg or {}).get("mt5", {}) if exec_cfg else {}

    prices_folder = (uni.get("folder") or "data/prices_1d")
    prices_folder = str((ROOT / prices_folder).resolve())
    costs_csv = (uni.get("costs_csv") or "data/costs_per_symbol.csv")
    costs_csv = str((ROOT / costs_csv).resolve())

    lookback_years = int(uni.get("lookback_years", 5))

    # risk & weights
    risk = cfg.get("risk", {})
    weights = cfg.get("weights", {})
    volcarry = cfg.get("volcarry", {})
    mtd = cfg.get("mtd_gates", {})
    sanity = cfg.get("trade_sanity", {})

    # output
    base_prefix = out_cfg.get("out_prefix_base", "DAILY")
    today_tag = _ts_utc_now().strftime("%Y%m%d")
    out_prefix = args.out_prefix or f"{base_prefix}_{today_tag}"

    # compute start/end from lookback
    end_utc = _ts_utc_now().normalize()
    start_utc = (end_utc - pd.DateOffset(years=lookback_years)).normalize()

    # --- 1) Backtest to generate up-to-date signals
    bt_cmd = [
        sys.executable, "-m", "src.exec.backtest_pnl_demo",
        "--folder", prices_folder,
        "--costs_csv", costs_csv,
        "--out_prefix", out_prefix,
        "--target_ann_vol", str(risk.get("target_ann_vol", 0.15)),
        "--vol_lookback", str(risk.get("vol_lookback", 30)),
        "--max_leverage", str(risk.get("max_leverage", 3.0)),
        "--w_tsmom", str(weights.get("tsmom", 1.0)),
        "--w_xsec", str(weights.get("xsec", 0.8)),
        "--w_mr", str(weights.get("mr", 0.6)),
        "--w_volcarry", str(weights.get("volcarry", cfg.get("weights", {}).get("volcarry", 0.0))),
        "--volcarry_top_q", str(volcarry.get("top_q", 0.25)),
        "--volcarry_bot_q", str(volcarry.get("bot_q", 0.25)),
        "--volcarry_lookback", str(volcarry.get("lookback", 42)),
        "--mtd_soft", str(mtd.get("soft", -0.06)),
        "--mtd_hard", str(mtd.get("hard", -0.10)),
        "--start", start_utc.strftime("%Y-%m-%d"),
        "--end", end_utc.strftime("%Y-%m-%d"),
    ]

    # Optional sanity/gap settings (only pass if present)
    if "gap_atr_k" in sanity:
        bt_cmd += ["--gap_atr_k", str(sanity["gap_atr_k"])]
    if "atr_lookback" in sanity:
        bt_cmd += ["--atr_lookback", str(sanity["atr_lookback"])]
    if "vol_spike_mult" in sanity:
        bt_cmd += ["--vol_spike_mult", str(sanity["vol_spike_mult"])]
    if "vol_spike_window" in sanity:
        bt_cmd += ["--vol_spike_window", str(sanity["vol_spike_window"])]

    run(bt_cmd, check=True)

    # The backtester writes data/{prefix}_positions.csv – use that as the source of truth
    positions_snap = DATA / f"{out_prefix}_positions.csv"
    if not positions_snap.exists():
        # fallback: maybe backtester didn’t write snapshot; try signals/positions.csv
        fallback_pos = SIGNALS / "positions.csv"
        if not fallback_pos.exists():
            raise FileNotFoundError(f"No positions snapshot found: {positions_snap} (and no fallback at {fallback_pos})")
        pos_src = fallback_pos
    else:
        pos_src = positions_snap

    # Write positions to signals/positions.csv
    SIGNALS.mkdir(parents=True, exist_ok=True)
    dest_positions = SIGNALS / "positions.csv"
    shutil.copyfile(pos_src, dest_positions)
    print(f"Saved positions to {dest_positions}")

    # --- 2) Make orders (if enabled)
    orders_enabled = bool(orders_cfg.get("enabled", True))
    wrote_orders = False
    orders_out = (orders_cfg.get("out_csv") or "signals/orders.csv")
    orders_out = str((ROOT / orders_out).resolve())

    if orders_enabled:
        contracts_csv = (orders_cfg.get("contracts_csv") or "config/contracts.csv")
        contracts_csv = str((ROOT / contracts_csv).resolve())
        max_age = int(orders_cfg.get("max_price_age_days", 7))
        nav = float(orders_cfg.get("nav", 1_000_000))
        gross_cap = float(orders_cfg.get("gross_cap", 3.0))

        mk_cmd = [
            sys.executable, "-m", "src.exec.make_orders",
            "--positions_csv", str(dest_positions.resolve()),
            "--contracts_csv", contracts_csv,
            "--prices_folder", prices_folder,
            "--out_csv", orders_out,
            "--nav", str(nav),
            "--gross_cap", str(gross_cap),
            "--max_price_age_days", str(max_age),
        ]
        try:
            run(mk_cmd, check=True)
            print(f"Orders file written (paper): {orders_out}")
            wrote_orders = True
        except sp.CalledProcessError as e:
            print(f"Orders generation failed: {e}", file=sys.stderr)

    # --- 3) Publish to MT5 (if enabled AND orders exist)
    exec_enabled = bool(exec_cfg.get("enabled", False))
    publish_ok = False
    if exec_enabled and wrote_orders:
        broker = str(exec_cfg.get("broker", "mt5")).lower()
        dry_run = str(exec_cfg.get("dry_run", True)).lower() in ("1", "true", "yes")
        if broker != "mt5":
            print(f"Execution enabled but broker '{broker}' != 'mt5' – skipping publish.")
        else:
            pub_cmd = [
                sys.executable, "-m", "src.exec.publish_mt5",
                "--orders_csv", orders_out,
                "--contracts_csv", str((ROOT / mt5_cfg.get("contracts_csv", "config/contracts.csv")).resolve()),
                "--dry_run", str(dry_run).lower(),
            ]

            # (Optional) Pass alias map if present (file path, not required)
            # If your publish_mt5 reads alias/max lot from YAML itself you can skip.
            try:
                run(pub_cmd, check=True)
                publish_ok = True
            except sp.CalledProcessError as e:
                print(f"MT5 publish failed: {e}", file=sys.stderr)

    # --- 4) Summary (minimal console + optional Slack/Email stubs)
    try:
        eq_path = DATA / f"{out_prefix}_equity.csv"
        if eq_path.exists():
            eq = pd.read_csv(eq_path, parse_dates=["ts"])
            # normalize timestamp to UTC tz-aware
            eq["ts"] = pd.to_datetime(eq["ts"], utc=True, errors="coerce")
            eq = eq.dropna(subset=["ts"]).set_index("ts").sort_index()

            # pick the equity column (fallbacks for alternate names)
            eq_col = None
            for cand in ("portfolio_equity", "equity", "Equity"):
                if cand in eq.columns:
                    eq_col = cand
                    break

            if eq_col and not eq.empty:
                # Make PeriodIndex monthly without warning:
                # 1) ensure tz-aware UTC (already done)
                # 2) strip tz to naive
                idx_naive = eq.index.tz_localize(None)
                per = idx_naive.to_period("M")

                # latest (current) month slice
                last_month = per[-1]
                eq_month = eq.loc[per == last_month, eq_col]

                if not eq_month.empty:
                    start_eq = float(eq_month.iloc[0])
                    end_eq   = float(eq_month.iloc[-1])
                    if start_eq > 0:
                        mtd = (end_eq / start_eq) - 1.0
                        print(f"[DAILY] MTD: {mtd:.2%} | Last {len(eq_month)} obs.")
                    else:
                        print(f"[DAILY] MTD: n/a (start equity <= 0) | Last {len(eq_month)} obs.")
            else:
                print("[DAILY] MTD: n/a (no equity column or empty file)")
    except Exception as ex:
        print(f"WARN: summary failed: {ex}", file=sys.stderr)

    # Slack/email are optional and depend on your utils; keep warnings quiet:
    # (You can wire your own notify here later)

print("[DAILY] Done.")
if __name__ == "__main__":
    main()