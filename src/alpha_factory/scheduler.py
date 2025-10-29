from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List
import os
import sys
import json
import pathlib
import runpy
import time

JobFunc = Callable[[], None]


@dataclass
class Job:
    name: str
    func: JobFunc
    deps: tuple[str, ...] = ()


class Scheduler:
    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}

    def register(self, name: str, func: JobFunc, deps: Iterable[str] = ()) -> None:
        if name in self._jobs:
            raise ValueError(f"Job already registered: {name}")
        self._jobs[name] = Job(name=name, func=func, deps=tuple(deps))

    def run(self, targets: Iterable[str]) -> None:
        # topo sort with simple DFS
        seen: Dict[str, int] = {}  # 0=unseen,1=visiting,2=done
        order: List[str] = []

        def dfs(n: str) -> None:
            state = seen.get(n, 0)
            if state == 1:
                raise RuntimeError(f"Cycle in job deps at {n}")
            if state == 2:
                return
            if n not in self._jobs:
                raise KeyError(f"Unknown job: {n}")
            seen[n] = 1
            for d in self._jobs[n].deps:
                dfs(d)
            order.append(n)
            seen[n] = 2

        for t in targets:
            dfs(t)

        for name in order:
            t0 = time.time()
            print(f"[scheduler] ▶ {name}")
            self._jobs[name].func()
            dt = time.time() - t0
            print(f"[scheduler] ✅ {name} ({dt:.2f}s)")


# ---------- Built-in jobs (file-based, no network) ----------


def _env_list(key: str, default: str) -> list[str]:
    return [x for x in os.getenv(key, default).split(",") if x]


def job_ensure_meta_metrics() -> None:
    """Create configs/meta_metrics.json if missing, with a safe default."""
    cfg = pathlib.Path("configs")
    cfg.mkdir(parents=True, exist_ok=True)
    path = cfg / "meta_metrics.json"
    if not path.exists():
        path.write_text(
            json.dumps(
                {
                    "TF": {"sharpe": 1.2, "dd": 0.06},
                    "MR": {"sharpe": 1.0, "dd": 0.05},
                    "VOL": {"sharpe": 0.8, "dd": 0.04},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"[scheduler] wrote default {path}")
    else:
        print(f"[scheduler] metrics present: {path}")


def _run_cli_file(path: str, argv: list[str]) -> None:
    src = pathlib.Path("src").resolve()
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    # Save/restore argv
    prev = sys.argv[:]
    try:
        sys.argv = argv
        runpy.run_path(path, run_name="__main__")
    finally:
        sys.argv = prev


def job_meta_allocator() -> None:  # redefine with helper
    _run_cli_file(
        "src/alpha_factory/cli_meta_alloc.py",
        [
            "cli_meta_alloc.py",
            "--mode",
            os.getenv("AF_ALLOC_MODE", "ewma"),
            "--metrics",
            os.getenv("AF_METRICS_PATH", "configs/meta_metrics.json"),
            "--outdir",
            os.getenv("AF_ALLOC_OUT", "artifacts/allocations"),
            "--write-latest",
        ],
    )


def job_emit_targets() -> None:
    """Emit portfolio targets from latest allocations. Assets via env."""
    assets = _env_list("AF_ASSETS", "EURUSD,GBPUSD,USDJPY")
    cap = os.getenv("AF_CAP", "1.0")
    per_asset_cap = os.getenv("AF_PER_ASSET_CAP", "0.5")
    out = os.getenv("AF_TARGETS_OUT", "artifacts/targets/latest.csv")
    alloc_dir = os.getenv("AF_ALLOC_OUT", "artifacts/allocations")
    _run_cli_file(
        "src/alpha_factory/cli_targets.py",
        [
            "cli_targets.py",
            "--alloc-dir",
            alloc_dir,
            "--assets",
            *assets,
            "--cap",
            cap,
            "--per-asset-cap",
            per_asset_cap,
            "--out",
            out,
        ],
    )


def make_default_scheduler() -> Scheduler:
    s = Scheduler()
    s.register("ensure_metrics", job_ensure_meta_metrics)
    s.register("meta_alloc", job_meta_allocator, deps=("ensure_metrics",))
    s.register("emit_targets", job_emit_targets, deps=("meta_alloc",))
    # A convenience meta-job
    s.register("nightly", lambda: s.run(("emit_targets",)))
    return s
