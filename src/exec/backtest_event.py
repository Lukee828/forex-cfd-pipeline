# src/exec/backtest_event.py
import argparse
from datetime import datetime, UTC

from src.backtest.engine_loop import run_loop


class _NoOpFeed:
    def __init__(self, steps: int) -> None:
        self._n = steps
        self._i = 0

    class _Ev:
        def __init__(self, ts):
            self.ts = ts

    def next_bar(self):
        if self._i >= self._n:
            return None
        self._i += 1
        return self._Ev(datetime.now(UTC))


class _NoOpStrategy:
    def on_market(self, event):  # returns no signals
        return []


class _NoOpPortfolio:
    def on_market(self, event):
        pass

    def on_signal(self, sig):
        return None

    def on_fill(self, fill):
        pass


class _NoOpExecution:
    def execute(self, order):
        return order  # pretend filled, same shape


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", required=False, help="(unused for now) config path")
    ap.add_argument("--start", required=False)
    ap.add_argument("--end", required=False)
    ap.add_argument(
        "--steps", type=int, default=25, help="how many market ticks to simulate (noop)"
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    steps = run_loop(
        _NoOpFeed(args.steps), _NoOpStrategy(), _NoOpPortfolio(), _NoOpExecution()
    )
    print(f"[event-driven] OK — processed {steps} market steps (noop).")
    if args.dry_run:
        print("[D R Y   R U N] no outputs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
