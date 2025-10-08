from __future__ import annotations
import argparse
import importlib
import json
import cProfile
import pstats
import io
import sys


def _import_func(qual: str):
    # "package.module:func"
    if ":" not in qual:
        raise SystemExit("Use MODULE_PATH:FUNC_NAME (e.g. src.exec.backtest:main)")
    mod_path, func_name = qual.split(":", 1)
    mod = importlib.import_module(mod_path)
    fn = getattr(mod, func_name)
    return fn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True, help="module.path:func")
    ap.add_argument("--args", default="[]", help="JSON list for *args")
    ap.add_argument("--kwargs", default="{}", help="JSON dict for **kwargs")
    ap.add_argument("--out", default="profile.stats", help="cProfile output file")
    ap.add_argument("--top", type=int, default=30, help="lines to show")
    ns = ap.parse_args()

    args = json.loads(ns.args)
    kwargs = json.loads(ns.kwargs)

    fn = _import_func(ns.target)

    pr = cProfile.Profile()
    pr.enable()
    try:
        fn(*args, **kwargs)
    finally:
        pr.disable()
        pr.dump_stats(ns.out)

    s = io.StringIO()
    p = pstats.Stats(ns.out, stream=s).sort_stats("cumtime")
    p.print_stats(ns.top)
    sys.stdout.write(s.getvalue())


if __name__ == "__main__":
    main()
