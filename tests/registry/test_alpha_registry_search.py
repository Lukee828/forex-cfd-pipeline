from pathlib import Path
from src.registry.alpha_registry import AlphaRegistry


def test_search_min_max_and_tag(tmp_path: Path):
    db = tmp_path / "registry.duckdb"
    reg = AlphaRegistry(db).init()

    reg.register("cfgA", {"sharpe": 0.6, "ret": 0.12}, ["fx", "m5"])
    reg.register("cfgB", {"sharpe": 1.2, "ret": 0.18}, ["fx", "h1"])
    reg.register("cfgC", {"sharpe": 1.5, "ret": 0.09}, ["alt"])
    reg.register("cfgD", {"sharpe": 0.9, "ret": 0.25}, ["fx"])

    # sharpe >= 1.0 (no tag)
    got = reg.search("sharpe", min=1.0, limit=10)
    scores = [round(r[5], 3) for r in got]  # score column
    assert scores == [1.5, 1.2]

    # sharpe >= 0.8 and <= 1.0, fx only
    got2 = reg.search("sharpe", min=0.8, max=1.0, tag="fx", limit=10)
    ids = [r[0] for r in got2]
    # only cfgD qualifies (0.9, tag fx)
    assert len(ids) == 1

    # ret between 0.1 and 0.2, fx only
    got3 = reg.search("ret", min=0.1, max=0.2, tag="fx", limit=10)
    hashes = [r[2] for r in got3]
    assert set(hashes) == {"cfgA", "cfgB"}
