# tests/alpha_factory/test_live_guard_config.py
from __future__ import annotations

from pathlib import Path
from alpha_factory.live_guard_config import (
    load_config,
    save_config,
    LiveConfig,
    mark_breach,
    breach_exists,
)


def test_config_roundtrip_and_defaults(tmp_path: Path):
    # first load should create defaults file if missing
    cfg1 = load_config(tmp_path)
    assert cfg1.live_enabled is False
    assert cfg1.max_spread_pips > 0
    assert cfg1.max_latency_sec > 0

    # flip live_enabled and save
    cfg2 = LiveConfig(
        live_enabled=True,
        max_spread_pips=1.2,
        max_slippage_pips=0.9,
        max_latency_sec=1.5,
    )
    save_config(tmp_path, cfg2)

    # reload should match what we saved
    cfg3 = load_config(tmp_path)
    assert cfg3.live_enabled is True
    assert cfg3.max_spread_pips == 1.2
    assert cfg3.max_slippage_pips == 0.9
    assert cfg3.max_latency_sec == 1.5


def test_breach_flag(tmp_path: Path):
    assert breach_exists(tmp_path) is False
    mark_breach(tmp_path, "slippage too high")
    assert breach_exists(tmp_path) is True

    # sanity: BREACH.txt actually has reason string
    p = tmp_path / "artifacts" / "live" / "BREACH.txt"
    body = p.read_text(encoding="utf-8")
    assert "slippage too high" in body
