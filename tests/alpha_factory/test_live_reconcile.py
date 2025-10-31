from pathlib import Path
from alpha_factory.bridge_contract import record_fill_from_ea, write_intent_row
from alpha_factory.live_reconcile import (
    _read_journal,
    pair_intents_and_fills,
    summarize_execution_quality,
)

def test_reconcile_pairs_and_summary(tmp_path: Path):
    # prepare fake journal with INTENT then FILL
    live_dir = tmp_path / "artifacts" / "live"
    live_dir.mkdir(parents=True)

    # pretend LiveGuard wrote an INTENT
    write_intent_row(
        live_dir,
        symbol="EURUSD",
        side="BUY",
        size=0.40,
        price_request=1.08650,
        note="risk_ok",
    )

    # pretend EA executed 0.32 a moment later
    record_fill_from_ea(
        repo_root=tmp_path,
        symbol="EURUSD",
        side="BUY",
        size=0.32,
        price_exec=1.08652,
        ticket_id="T123",
        note="ok",
    )

    rows = _read_journal(live_dir / "journal.ndjson")
    assert any(r["type"] == "INTENT" for r in rows)
    assert any(r["type"] == "FILL" for r in rows)

    pairs = pair_intents_and_fills(rows)
    assert len(pairs) == 1
    p = pairs[0]
    assert p["status"] in ("FILLED", "PARTIAL")
    assert p["fill_size"] == 0.32

    summary = summarize_execution_quality(pairs)
    assert summary["n_intents"] == 1
    assert summary["n_fills"] == 1
    assert 0.0 <= summary["fill_ratio"] <= 1.0