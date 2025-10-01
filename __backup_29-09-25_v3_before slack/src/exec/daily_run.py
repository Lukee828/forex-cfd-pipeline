# src/exec/daily_run.py
import argparse
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import yaml
from src.utils.notify import send_email


ROOT = Path(r"C:\Users\speed\Desktop\Forex CFD's system")  # adjust if needed


def run_backtest(folder, costs_csv, start, end, params, out_prefix):
    cmd = [
        sys.executable,
        "-m",
        "src.exec.backtest_pnl_demo",
        "--folder",
        str(folder),
        "--costs_csv",
        str(costs_csv),
        "--target_ann_vol",
        str(params["risk"]["target_ann_vol"]),
        "--vol_lookback",
        str(params["risk"]["vol_lookback"]),
        "--max_leverage",
        str(params["risk"]["max_leverage"]),
        "--w_tsmom",
        str(params["weights"].get("tsmom", 1.0)),
        "--w_xsec",
        str(params["weights"].get("xsec", 0.8)),
        "--w_mr",
        str(params["weights"].get("mr", 0.6)),
        "--w_volcarry",
        str(params["weights"].get("volcarry", 0.0)),
        "--volcarry_top_q",
        str(params["volcarry"].get("top_q", 0.35)),
        "--volcarry_bot_q",
        str(params["volcarry"].get("bot_q", 0.35)),
        "--volcarry_lookback",
        str(params["volcarry"].get("lookback", 63)),
        "--mtd_soft",
        str(params["mtd_gates"].get("soft", -0.06)),
        "--mtd_hard",
        str(params["mtd_gates"].get("hard", -0.10)),
        "--gap_atr_k",
        str(params["trade_sanity"].get("gap_atr_k", 3.0)),
        "--atr_lookback",
        str(params["trade_sanity"].get("atr_lookback", 14)),
        "--vol_spike_mult",
        str(params["trade_sanity"].get("vol_spike_mult", 3.0)),
        "--vol_spike_window",
        str(params["trade_sanity"].get("vol_spike_window", 60)),
        "--out_prefix",
        out_prefix,
        "--start",
        start,
        "--end",
        end,
    ]
    print("RUN:", " ".join(cmd))
    cp = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    if cp.returncode != 0:
        print(cp.stdout, cp.stderr)
        raise SystemExit("Backtest failed")
    eq_csv = ROOT / "data" / f"{out_prefix}_equity.csv"
    tr_csv = ROOT / "data" / f"{out_prefix}_trades.csv"
    return eq_csv, tr_csv


def make_positions_from_trades(trades_csv: Path, out_csv: Path):
    import numpy as np

    tr = pd.read_csv(
        trades_csv, parse_dates=["exit_time", "entry_time"], dayfirst=False
    )
    cols = {c.lower(): c for c in tr.columns}
    pos_series = None
    if "position" in cols:
        pos_series = tr[cols["position"]]
    elif "qty" in cols:
        q = pd.to_numeric(tr[cols["qty"]], errors="coerce").fillna(0.0)
        pos_series = q.clip(-1, 1)
    elif "side" in cols:
        side_map = {"long": 1.0, "short": -1.0, "buy": 1.0, "sell": -1.0}
        pos_series = tr[cols["side"]].astype(str).str.lower().map(side_map).fillna(0.0)
    elif "dir" in cols:
        d = pd.to_numeric(tr[cols["dir"]], errors="coerce").fillna(0.0)
        pos_series = np.sign(d).clip(-1, 1)

    if pos_series is None:
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=["symbol", "position", "asof_utc"]).to_csv(
            out_csv, index=False
        )
        print("Trades CSV lacks position/qty/side/dir; wrote flat positions:", out_csv)
        return

    tr = tr.assign(_position=pos_series)
    order_col = (
        "exit_time"
        if "exit_time" in tr.columns
        else ("entry_time" if "entry_time" in tr.columns else None)
    )
    if order_col:
        tr = tr.sort_values(["symbol", order_col])
    last = (
        tr.groupby("symbol", as_index=False)
        .tail(1)[["symbol", "_position"]]
        .rename(columns={"_position": "position"})
    )
    last["asof_utc"] = datetime.utcnow().isoformat() + "Z"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    last.to_csv(out_csv, index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "config" / "production.yaml"))
    ap.add_argument("--asof", default=None, help="YYYY-MM-DD (UTC date)")
    ap.add_argument("--out_prefix", default=None)
    args = ap.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        raise SystemExit(f"Missing config: {cfg_path}")
    params = yaml.safe_load(cfg_path.read_text())

    # dates
    if args.asof:
        asof = pd.Timestamp(args.asof).tz_localize("UTC")
    else:
        asof = pd.Timestamp.utcnow().tz_convert("UTC")
    start = (
        asof - pd.Timedelta(days=365 * int(params["universe"].get("lookback_years", 5)))
    ).strftime("%Y-%m-%d")
    end = asof.strftime("%Y-%m-%d")

    # paths
    folder = ROOT / params["universe"]["folder"]
    costs_csv = ROOT / params["universe"]["costs_csv"]
    out_base = params.get("output", {}).get("out_prefix_base", "DAILY")
    out_prefix = args.out_prefix or f"{out_base}_{asof.strftime('%Y%m%d')}"
    positions_csv = ROOT / params.get("output", {}).get(
        "positions_csv", "signals/positions.csv"
    )

    eq_csv, tr_csv = run_backtest(folder, costs_csv, start, end, params, out_prefix)

    # MTD check (tz-safe, no warnings)
    eq = pd.read_csv(eq_csv, parse_dates=["ts"]).set_index("ts")
    idx_utc = eq.index if eq.index.tz is None else eq.index.tz_convert("UTC")
    per = idx_utc.to_period("M")
    eq_month = eq[per == per[-1]]
    mtd = (
        eq_month["portfolio_equity"].iloc[-1] / eq_month["portfolio_equity"].iloc[0] - 1
    )
    hard = float(params["mtd_gates"].get("hard", -0.10))
    if mtd <= hard:
        print(
            f"MTD hard stop breached ({mtd:.2%} <= {hard:.2%}); writing zero positions."
        )
        positions_csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=["symbol", "position", "asof_utc"]).to_csv(
            positions_csv, index=False
        )
        return

    hard = float(params["mtd_gates"].get("hard", -0.10))
    if mtd <= hard:
        positions_csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=["symbol", "position", "asof_utc"]).to_csv(
            positions_csv, index=False
        )
        # Email alert
        body_txt = f"MTD HARD BREACH\nOut prefix: {out_prefix}\nMTD: {mtd:.2%} (hard: {hard:.2%})\nPositions flattened -> {positions_csv}"
        body_html = f"""<h3>MTD HARD BREACH</h3>
        <p><b>Out prefix:</b> {out_prefix}<br>
        <b>MTD:</b> {mtd:.2%} (hard: {hard:.2%})<br>
        <b>Positions:</b> {positions_csv}</p>"""
        send_email(
            subject=f"[DAILY] MTD HARD BREACH {out_prefix}",
            body_text=body_txt,
            body_html=body_html,
        )
        return

    # positions: prefer backtester snapshot
    backtester_pos = ROOT / "data" / f"{out_prefix}_positions.csv"
    positions_csv.parent.mkdir(parents=True, exist_ok=True)
    if backtester_pos.exists():
        print("Using positions snapshot from backtester:", backtester_pos)
        positions_csv.write_text(backtester_pos.read_text())
    else:
        print("No positions snapshot found, falling back to trades inference")
        make_positions_from_trades(tr_csv, positions_csv)

    print("Saved positions to", positions_csv)

    # Build a tiny HTML/text summary
    eq_tail = eq.tail(1)["portfolio_equity"].iloc[0]
    start_date = eq.index[0].date()
    end_date = eq.index[-1].date()
    mtd_str = f"{mtd:.2%}"

    body_txt = (
        f"DAILY RUN OK\n"
        f"Out prefix: {out_prefix}\n"
        f"Period: {start_date} -> {end_date}\n"
        f"Equity (last): {eq_tail:.4f}\n"
        f"MTD: {mtd_str}\n"
        f"Positions: {positions_csv}"
    )
    body_html = f"""<h3>DAILY RUN OK</h3>
    <p><b>Out prefix:</b> {out_prefix}<br>
    <b>Period:</b> {start_date} → {end_date}<br>
    <b>Equity (last):</b> {eq_tail:.4f}<br>
    <b>MTD:</b> {mtd_str}<br>
    <b>Positions:</b> {positions_csv}</p>"""

    send_email(
        subject=f"[DAILY] run OK {out_prefix}", body_text=body_txt, body_html=body_html
    )

    report_dir = ROOT / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / f"{out_prefix}_summary.html"
    report_file.write_text(body_html, encoding="utf-8")
    print("Saved daily HTML summary:", report_file)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        try:
            send_email(
                subject="[DAILY] run FAILED",
                body_text=str(e),
                body_html=f"<pre>{e}</pre>",
            )
        except Exception:
            pass
        raise
