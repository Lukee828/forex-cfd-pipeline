#!/usr/bin/env python
# tools/analyze_config.py
import argparse
import sys
from pathlib import Path

try:
    import yaml
except Exception:
    print(
        "ERROR: PyYAML not installed. Run: .\\.venv\\Scripts\\python.exe -m pip install pyyaml",
        file=sys.stderr,
    )
    sys.exit(2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", default="config/production.yaml")
    args = ap.parse_args()

    p = Path(args.cfg)
    if not p.exists():
        print(f"CONFIG: {p} (missing)")
        return 0

    cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    print(f"CONFIG: {p} (loaded)\n")

    sym = cfg.get("symbols", {})
    core = sym.get("core")
    sat = sym.get("satellite")

    print("--- DIAGNOSTICS ---")
    print(f"symbols.core: {core if core is not None else '(missing)'}")
    print(f"symbols.satellite: {sat if sat is not None else '(missing)'}")
    print("\nTop-level keys:", list(cfg.keys()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
