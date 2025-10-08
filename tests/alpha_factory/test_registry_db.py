import sqlite3
from src.alpha_factory import registry
from src.alpha_factory.registry_db import (
    init_db,
    sync_from_registry,
    list_factors,
    clear_all,
)


def test_registry_sync_roundtrip(tmp_path):
    db = tmp_path / "alpha_registry.db"
    conn = sqlite3.connect(db)
    init_db(conn)
    clear_all(conn)

    n = sync_from_registry(registry, conn)
    assert n >= 1

    rows = list_factors(conn)
    names = [name for (name, _) in rows]
    for expected in registry.names():
        assert expected in names
