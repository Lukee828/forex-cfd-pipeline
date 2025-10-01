import argparse
import yaml


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", required=True)
    ap.add_argument("--start", default="2019-01-01")
    ap.add_argument("--end", default="2024-12-31")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(args.cfg, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)

    if args.dry_run:
        print(
            "Config loaded OK. Symbols:",
            cfg["symbols"]["core"][:3],
            "... +",
            len(cfg["symbols"]["satellite"]),
            "satellites",
        )
        return 0
    print("Backtest harness placeholder — wire data & sleeves next.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
