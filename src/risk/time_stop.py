from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone

__all__ = ["TimeStopConfig", "bars_elapsed", "should_time_stop", "is_time_stop"]


@dataclass(frozen=True)
class TimeStopConfig:
    max_bars: int = 0
    max_days: int = 0


def bars_elapsed(entry_dt: datetime, now_dt: datetime, bar_minutes: int) -> int:
    """Return completed bars between entry and now (>= 0)."""
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)
    if entry_dt.tzinfo is None:
        entry_dt = entry_dt.replace(tzinfo=timezone.utc)
    if bar_minutes <= 0:
        raise ValueError("bar_minutes must be > 0")
    diff_sec = (now_dt - entry_dt).total_seconds()
    return int(max(0, diff_sec // (bar_minutes * 60)))


def should_time_stop(
    entry_dt: datetime,
    now_dt: datetime,
    bar_minutes: int,
    cfg: TimeStopConfig,
) -> tuple[bool, int, int]:
    """Return (stop?, bars_elapsed, days_elapsed) given config thresholds."""
    b = bars_elapsed(entry_dt, now_dt, bar_minutes)
    d = (now_dt.date() - entry_dt.date()).days
    hit_bars = cfg.max_bars > 0 and b >= cfg.max_bars
    hit_days = cfg.max_days > 0 and d >= cfg.max_days
    return (hit_bars or hit_days, b, d)


# --- Back-compat alias override (appended by tooling) ---
def is_time_stop(bars_elapsed: int, days_elapsed: int, cfg: "TimeStopConfig"):
    """Back-compat alias for overlays & tools expecting is_time_stop(bars, days, cfg)."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(tz=timezone.utc)
    entry = now - timedelta(
        days=days_elapsed, minutes=bars_elapsed * 60
    )  # assume 60m bars
    return should_time_stop(entry, now, bar_minutes=60, cfg=cfg)
