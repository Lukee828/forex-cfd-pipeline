from pathlib import Path

from src.registry.alpha_registry import AlphaRegistry


def test_register_and_best(tmp_path: Path):
    db = tmp_path / "registry.duckdb"
    reg = AlphaRegistry(db).init()

    a1 = reg.register("cfgA", {"sharpe": 1.0, "ret": 0.15}, ["fx", "h1"])
    a2 = reg.register("cfgB", {"sharpe": 1.5, "ret": 0.12}, ["fx"])
    a3 = reg.register("cfgC", {"sharpe": 0.5, "ret": 0.20}, ["alt"])

    assert a1 == 1
    assert a2 == 2
    assert a3 == 3

    top2 = reg.get_best("sharpe", 2)
    # rows: (id, ts, config_hash, metrics, tags, score)
    assert [row[0] for row in top2] == [2, 1]
    assert [round(row[5], 3) for row in top2] == [1.5, 1.0]


def test_list_recent_and_tags(tmp_path: Path):
    db = tmp_path / "registry.duckdb"
    reg = AlphaRegistry(db).init()

    reg.register("cfgX", {"sharpe": 0.7}, ["fx", "m5"])
    reg.register("cfgY", {"sharpe": 0.9}, ["equity"])
    reg.register("cfgZ", {"sharpe": 1.1}, ["fx", "h1"])

    recent_all = reg.list_recent(limit=10)
    assert len(recent_all) == 3
    # newest first => last insert id should be first
    assert recent_all[0][0] == 3

    recent_fx = reg.list_recent(tag="fx", limit=10)
    assert len(recent_fx) == 2
    ids = {row[0] for row in recent_fx}
    assert ids == {1, 3}
