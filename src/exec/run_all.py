from __future__ import annotations
import argparse
import sys


def _no_subprocess(*args, **kwargs):
    raise RuntimeError("Blocked by local-only policy: subprocess is disabled")


def _no_subprocess(*args, **kwargs):
    raise RuntimeError("Blocked by local-only policy: subprocess is disabled")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", required=True)
    ap.add_argument("--folder", required=True)
    ap.add_argument("--costs_csv", default="data/costs_per_symbol.csv")
    ap.add_argument("--target_ann_vol", type=float, default=0.12)
    ap.add_argument("--vol_lookback", type=int, default=20)
    ap.add_argument("--max_leverage", type=float, default=3.0)
    ap.add_argument("--mtd_soft", type=float, default=-0.06)
    ap.add_argument("--mtd_hard", type=float, default=-0.10)
    ap.add_argument("--w_tsmom", type=float, default=1.0)
    ap.add_argument("--w_xsec", type=float, default=0.8)
    ap.add_argument("--w_mr", type=float, default=0.6)
    ap.add_argument("--w_volcarry", type=float, default=0.4)
    ap.add_argument("--nav", type=float, default=1_000_000.0)
    args = ap.parse_args()

    cmd = [
        sys.executable,
        "-m",
        "src.exec.backtest_pnl_demo",
        "--cfg",
        args.cfg,
        "--folder",
        args.folder,
        "--costs_csv",
        args.costs_csv,
        "--target_ann_vol",
        str(args.target_ann_vol),
        "--vol_lookback",
        str(args.vol_lookback),
        "--max_leverage",
        str(args.max_leverage),
        "--mtd_soft",
        str(args.mtd_soft),
        "--mtd_hard",
        str(args.mtd_hard),
        "--w_tsmom",
        str(args.w_tsmom),
        "--w_xsec",
        str(args.w_xsec),
        "--w_mr",
        str(args.w_mr),
        "--w_volcarry",
        str(args.w_volcarry),
        "--nav",
        str(args.nav),
    ]

    print("Running:", " ".join(cmd))
    sys.exit(_no_subprocess(cmd))


if __name__ == "__main__":
    main()
