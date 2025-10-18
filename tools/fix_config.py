#!/usr/bin/env python
# tools/fix_config.py
import argparse
import sys
import re
from pathlib import Path
from datetime import datetime

try:
    import yaml
except Exception:
    print(
        "ERROR: PyYAML not installed. Run: .\\.venv\\Scripts\\python.exe -m pip install pyyaml",
        file=sys.stderr,
    )
    sys.exit(2)


def parse_list(s):
    if not s:
        return []
    return [x.strip().upper() for x in re.split(r"[,\s]+", s) if x.strip()]


def backup(path: Path):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path.with_suffix(path.suffix + f".bak_{ts}")
    bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return bak


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", default="config/production.yaml")
    ap.add_argument("--symbols", help="core symbols (comma/space separated)")
    ap.add_argument("--satellite", help="satellite symbols (comma/space separated); default empty")
    args = ap.parse_args()

    cfg_path = Path(args.cfg)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)

    if cfg_path.exists():
        try:
            cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        except Exception as e:
            print(f"ERROR: cannot parse YAML: {e}", file=sys.stderr)
            return 1
        bak = backup(cfg_path)
        print(f"Backed up -> {bak}")
    else:
        cfg = {}
        print(f"Starting new config -> {cfg_path}")

    cfg.setdefault("symbols", {})
    # core
    provided_core = parse_list(args.symbols)
    if provided_core:
        cfg["symbols"]["core"] = provided_core
    else:
        cfg["symbols"].setdefault("core", ["EURUSD", "GBPUSD", "USDJPY"])

    # satellite
    provided_sat = parse_list(args.satellite)
    if provided_sat or "satellite" not in cfg["symbols"]:
        cfg["symbols"]["satellite"] = provided_sat or []

    # write back
    cfg_yaml = yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True)
    cfg_path.write_text(cfg_yaml, encoding="utf-8")
    print(f"Wrote {cfg_path}")
    print("symbols.core     =", cfg["symbols"]["core"])
    print("symbols.satellite=", cfg["symbols"]["satellite"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
