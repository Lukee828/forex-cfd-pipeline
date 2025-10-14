from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Any, List, Tuple
import datetime as dt
import copy


# ----------------------------- Scheduling primitives ----------------------------- #


@dataclass
class Interval:
    seconds: int


@dataclass
class Daily:
    byhour: int = 0
    byminute: int = 0
    bysecond: int = 0


Schedule = Tuple[str, Any]  # ("interval", Interval) or ("daily", Daily)


def parse_schedule(cfg: Dict[str, Any]) -> Schedule:
    if "every" in cfg:
        sec = int(cfg["every"])
        if sec <= 0:
            raise ValueError("every must be > 0 seconds")
        return ("interval", Interval(seconds=sec))
    if "daily" in cfg:
        d = cfg["daily"] or {}
        return (
            "daily",
            Daily(
                byhour=int(d.get("byhour", 0)),
                byminute=int(d.get("byminute", 0)),
                bysecond=int(d.get("bysecond", 0)),
            ),
        )
    raise ValueError("Unknown schedule; provide either {'every': seconds} or {'daily': {...}}")


# ----------------------------- Deep-merge overlays ----------------------------- #


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge dicts: override wins; lists/atoms replaced; dicts merged recursively."""
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


# ----------------------------- Scheduler core ----------------------------- #


@dataclass
class Job:
    name: str
    func: Callable[..., Any]
    schedule: Schedule
    params: Dict[str, Any] = field(default_factory=dict)
    last_run: Optional[dt.datetime] = None
    next_run: Optional[dt.datetime] = None

    def compute_next_after(self, t: dt.datetime) -> dt.datetime:
        kind, spec = self.schedule
        if kind == "interval":
            # next strictly after t
            base = self.last_run or (t - dt.timedelta(seconds=spec.seconds))
            n = base
            while n <= t:
                n = n + dt.timedelta(seconds=spec.seconds)
            return n
        else:
            # daily at fixed time; if today time <= t, schedule tomorrow
            candidate = t.replace(
                hour=spec.byhour, minute=spec.byminute, second=spec.bysecond, microsecond=0
            )
            if candidate <= t:
                candidate = candidate + dt.timedelta(days=1)
            return candidate

    def due(self, now: dt.datetime) -> bool:
        # First-ever tick: run immediately, then compute next
        if self.last_run is None and self.next_run is None:
            self.next_run = now
        elif self.next_run is None:
            # Already ran before but next not set (edge), compute relative to now-1s
            self.next_run = self.compute_next_after(now - dt.timedelta(seconds=1))
        return now >= self.next_run

    def run(self, now: dt.datetime) -> Any:
        result = self.func(**self.params)
        self.last_run = now
        self.next_run = self.compute_next_after(now)
        return result


class ResearchScheduler:
    """
    Minimal stdlib scheduler:
      - supports ('every': seconds) or ('daily': {byhour, byminute, bysecond})
      - deep-merge overlays for config composition
      - pure pull-model via tick(now): returns list of (job_name, result)
    """

    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}

    def add_job(
        self,
        name: str,
        func: Callable[..., Any],
        sched_cfg: Dict[str, Any],
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        if name in self._jobs:
            raise ValueError(f"job '{name}' already exists")
        schedule = parse_schedule(sched_cfg)
        self._jobs[name] = Job(name=name, func=func, schedule=schedule, params=params or {})

    def tick(self, now: Optional[dt.datetime] = None) -> List[Tuple[str, Any]]:
        now = now or dt.datetime.utcnow()
        ran: List[Tuple[str, Any]] = []
        for job in self._jobs.values():
            if job.due(now):
                res = job.run(now)
                ran.append((job.name, res))
        return ran

    # -------- config helpers --------
    @staticmethod
    def merge_configs(base_cfg: Dict[str, Any], override_cfg: Dict[str, Any]) -> Dict[str, Any]:
        return deep_merge(base_cfg, override_cfg)

    @staticmethod
    def from_config(
        config: Dict[str, Any], registry: Dict[str, Callable[..., Any]]
    ) -> "ResearchScheduler":
        """
        config example:
        {
          "jobs": [
            {"name":"nightly_backtest", "task":"run_backtest", "schedule":{"daily":{"byhour":2}}},
            {"name":"pulse_prices", "task":"refresh_prices", "schedule":{"every": 900}, "params":{"universe":"majors"}}
          ]
        }
        """
        sch = ResearchScheduler()
        for job in config.get("jobs", []):
            name = job["name"]
            task_name = job["task"]
            if task_name not in registry:
                raise KeyError(f"Task '{task_name}' not found in registry")
            sch.add_job(name, registry[task_name], job["schedule"], params=job.get("params"))
        return sch
