from __future__ import annotations
import sys
import runpy
import pathlib


def _exec_src(rel_file: str) -> int:
    # repo root = two parents up from this file: alpha_factory/.. -> project root
    root = pathlib.Path(__file__).resolve().parents[1]
    target = root / "src" / "alpha_factory" / rel_file
    if not target.exists():
        sys.stderr.write(f"[shim] Missing target script: {target}\n")
        return 2
    # Run the real script as __main__ so its argparse behaves normally
    runpy.run_path(str(target), run_name="__main__")
    return 0


def main() -> int:
    # preserve sys.argv for the underlying script (runpy respects sys.argv)
    return _exec_src("registry_tooling.py")


if __name__ == "__main__":
    raise SystemExit(main())
