from __future__ import annotations

from pathlib import Path

from alpha_factory.bridge_contract import (
    build_live_safe_contract,
    append_trade_fill,
    _write_json,
)


def _write_cfg(tmp: Path, live_enabled: bool = False):
    cfg_path = tmp / "artifacts" / "live" / "live_guard_config.json"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(
        cfg_path,
        {
            "live_enabled": live_enabled,
            "max_spread_pips": 2.5,
            "max_age_sec": 5,
            "min_size": 0.05,
            "max_size": 1.0,
            "dup_window_sec": 30,
        },
    )


def test_contract_blocked_if_live_disabled_and_big_spread(tmp_path: Path):
    _write_cfg(tmp_path, live_enabled=False)

    # fake TradePlan dict
    tp = {
        "accept": True,
        "final_size": 0.5,
        "tp_pips": 15.0,
        "sl_pips": 10.0,
        "time_stop_bars": 50,
        "expected_value": 0.01,
        "reasons": ["base_accept"],
        "meta": {
            "symbol": "EURUSD",
        },
    }

    c = build_live_safe_contract(
        repo_root=tmp_path,
        tp_dict=tp,
        market_spread_pips=3.0,  # too wide
        model_age_sec=10.0,  # too stale
    )

    assert c["accept"] is False
    # We expect reasons to include live_disabled, spread_..., stale_..., etc.
    joined = " ".join(c["reasons"])
    assert "live_disabled" in joined
    assert "spread_" in joined
    assert "stale_" in joined
    assert c["size"] == 0.5


def test_duplicate_throttle(tmp_path: Path):
    _write_cfg(tmp_path, live_enabled=True)

    tp = {
        "accept": True,
        "final_size": 0.25,
        "tp_pips": 20.0,
        "sl_pips": 8.0,
        "time_stop_bars": 40,
        "expected_value": 0.02,
        "reasons": ["ok"],
        "meta": {
            "symbol": "EURUSD",
        },
    }

    # first call -> should "arm"
    c1 = build_live_safe_contract(
        repo_root=tmp_path,
        tp_dict=tp,
        market_spread_pips=1.0,
        model_age_sec=1.0,
    )
    assert c1["accept"] is True

    # immediate second call, same tp -> should be dup-blocked
    c2 = build_live_safe_contract(
        repo_root=tmp_path,
        tp_dict=tp,
        market_spread_pips=1.0,
        model_age_sec=1.0,
    )
    assert c2["accept"] is False
    assert any("duplicate_" in r for r in c2["reasons"])


def test_fill_append(tmp_path: Path):
    journal = tmp_path / "artifacts" / "live" / "journal.ndjson"
    journal.parent.mkdir(parents=True, exist_ok=True)

    append_trade_fill(
        journal_path=journal,
        ticket_id="MT5-12345",
        symbol="EURUSD",
        price_fill=1.08321,
        filled_size=0.30,
    )

    text = journal.read_text(encoding="utf-8").strip()
    assert '"event": "FILL"' in text
    assert '"ticket_id": "MT5-12345"' in text
    assert '"filled_size": 0.3' in text
