import alpha_factory.alpha_registry_ext_overrides_024  # install v0.2.4 overrides\nimport pandas as pd

# Install extensions (adds methods + auto "runs" view)
try:
    import alpha_factory.alpha_registry_ext  # noqa: F401
except Exception:
    pass

import inspect
import duckdb
import os


def _new_registry(db_path=":memory:"):
    from alpha_factory.alpha_registry import AlphaRegistry

    sig = inspect.signature(AlphaRegistry.__init__)
    params = sig.parameters
    # Construct
    if "path" in params:
        reg = AlphaRegistry(path=db_path)
    elif "db_path" in params:
        reg = AlphaRegistry(db_path=db_path)
    elif "database" in params:
        reg = AlphaRegistry(database=db_path)
    else:
        try:
            reg = AlphaRegistry()
        except TypeError:
            reg = AlphaRegistry(db_path)
    # Force internal path if present so register() uses our file
    for attr in ("db_path", "path", "database"):
        if hasattr(reg, attr):
            try:
                setattr(reg, attr, str(db_path))
            except Exception:
                pass
    return reg


def _ensure_alphas_schema(db_path: str):

    (
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        if db_path not in (":memory:", None, "")
        else None
    )
    con = duckdb.connect(db_path if db_path and db_path != ":memory:" else ":memory:")
    con.execute(
        """
    CREATE TABLE IF NOT EXISTS alphas (
      id           INTEGER,
      config_hash  TEXT,
      metrics      JSON,
      tags         TEXT,
      timestamp    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    )
    con.close()


def register_compat(reg, config_hash, metrics, tags):
    """Call reg.register with whatever signature it supports.
    Also ensure the 'alphas' table exists when using file-backed DBs.
    """
    # Try to detect a file-backed path so we can create schema there
    db_path = (
        getattr(reg, "db_path", None)
        or getattr(reg, "path", None)
        or getattr(reg, "database", None)
    )
    if isinstance(db_path, str) and db_path and db_path != ":memory:":
        _ensure_alphas_schema(db_path)

    # Try likely signatures in order:
    # 1) (config_hash, metrics, tags)
    try:
        return reg.register(config_hash, metrics, tags)
    except TypeError:
        pass

    # 2) keywords (most robust)
    try:
        return reg.register(config_hash=config_hash, metrics=metrics, tags=tags)
    except TypeError:
        pass

    # 3) (alpha_id, config_hash, metrics, tags) — rare; give alpha_id = config_hash alias
    try:
        return reg.register(config_hash, config_hash, metrics, tags)
    except TypeError:
        pass

    # 4) (alpha_id, metrics, tags) — then treat config_hash as alpha_id
    try:
        return reg.register(config_hash, metrics, tags)
    except TypeError as e:
        raise TypeError(f"Unsupported register(...) signature: {e}")


def test_rank_and_summary(tmp_path):
    db = tmp_path / "registry.duckdb"
    reg = _new_registry(str(db))

    register_compat(reg, "h1", {"sharpe": 2.1}, "brk,s2e")
    register_compat(reg, "h2", {"sharpe": 1.7}, "mom")

    ranked = reg.rank(metric="sharpe", top_n=2)
    assert hasattr(ranked, "shape") and len(ranked) == 2

    summary = reg.get_summary(metric="sharpe")
    assert any(k in summary.columns for k in ("mean", "max", "median"))


def test_lineage(tmp_path):
    db = tmp_path / "registry.duckdb"
    reg = _new_registry(str(db))
    run_id = reg.register_run(
        {
            "alpha_id": "s2e_brk",
            "run_hash": "r1",
            "timestamp": "2025-10-12T10:00:00Z",
            "source_version": "abc123",
            "config_hash": "h1",
            "config_diff": {"lr": 0.1},
            "tags": "exp,nightly",
        }
    )
    assert isinstance(run_id, str)
    lin = reg.get_lineage("s2e_brk")
    assert hasattr(lin, "shape") and len(lin) >= 1
