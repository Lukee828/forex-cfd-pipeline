from __future__ import annotations

import argparse
import sys

# Guarded import: never exit at import-time
try:
    import MetaTrader5 as mt5  # type: ignore

    _MT5_IMPORT_ERROR: Exception | None = None
except Exception as ex:  # pragma: no cover
    mt5 = None  # type: ignore[assignment]
    _MT5_IMPORT_ERROR = ex


def main(argv: list[str] | None = None) -> int:
    """
    Safe CLI wrapper for publishing orders to MT5.

    - Never exits at import time.
    - Defaults to --dry-run (especially in CI).
    - If MT5 isn't available and user requests live mode, returns a non-zero code
      but does not terminate the host shell.
    """
    ap = argparse.ArgumentParser(prog="publish_mt5", add_help=True)
    ap.add_argument(
        "--live", action="store_true", help="Enable live MT5 calls (disabled by default)."
    )
    ap.add_argument("--dry-run", action="store_true", help="Force dry-run mode (default).")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args(argv)

    # Default to dry-run unless user explicitly asks for --live.
    # (In CI we definitely want dry-run behavior.)
    dry_run = True if not args.live else False
    if args.dry_run:
        dry_run = True

    if dry_run:
        print("[publish_mt5] dry-run mode: MT5 calls are disabled; nothing will be sent.")
        if _MT5_IMPORT_ERROR is not None:
            print(
                f"[publish_mt5] Note: MetaTrader5 import failed: {_MT5_IMPORT_ERROR}",
                file=sys.stderr,
            )
        return 0

    # Live path: require a working MetaTrader5 module
    if mt5 is None:
        print(
            "[publish_mt5] ERROR: MetaTrader5 is not available; cannot run in --live mode.",
            file=sys.stderr,
        )
        if _MT5_IMPORT_ERROR is not None:
            print(f"[publish_mt5] Import error: {_MT5_IMPORT_ERROR}", file=sys.stderr)
        return 2

    # Minimal live skeleton (kept safe)
    if args.verbose:
        print("[publish_mt5] initializing MT5...")

    ok = False
    try:
        ok = mt5.initialize()
        if not ok:
            last_err = getattr(mt5, "last_error", lambda: ("unknown", ""))()
            print(f"[publish_mt5] initialize failed: {last_err}", file=sys.stderr)
            return 3

        # --- PLACEHOLDER: add real order logic here when you’re ready.
        print("[publish_mt5] live mode placeholder: no orders sent in this safe build.")
        return 0

    finally:
        if ok:
            try:
                mt5.shutdown()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
