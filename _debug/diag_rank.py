from tests.alpha_factory.test_registry_ext import _new_registry, register_compat
from importlib import import_module

# Ensure overrides load and patch AlphaRegistry
ov = import_module("alpha_factory.alpha_registry_ext_overrides_024")

# Use the same factory as the test


reg = _new_registry(":memory:")

# Register two rows (same as test)
register_compat(reg, "h1", {"sharpe": 2.1}, "brk,s2e")
register_compat(reg, "h2", {"sharpe": 1.7}, "mom")

# Use the EXACT connection the overrides will query
con = ov._con_for(reg)

print("--- duckdb_tables() ---")
try:
    for r in con.execute("SELECT name FROM duckdb_tables() ORDER BY name").fetchall():
        print("table:", r[0])
except Exception as e:
    print("duckdb_tables error:", e)

print("--- counts ---")
try:
    print("alphas rows:", con.execute("SELECT COUNT(*) FROM alphas").fetchone()[0])
except Exception as e:
    print("alphas missing:", e)

print("--- sample metric parse ---")
try:
    rows = con.execute(
        """
        SELECT
          config_hash,
          TRY_CAST(json_extract(CAST(metrics AS JSON), '$.sharpe') AS DOUBLE) AS sharpe
        FROM alphas
        ORDER BY config_hash
    """
    ).fetchall()
    print(rows)
except Exception as e:
    print("metric parse error:", e)

print("--- rank() result ---")
ranked = reg.rank(metric="sharpe", top_n=2)
print(type(ranked), getattr(ranked, "shape", None))
try:
    print(ranked.head())
except Exception:
    pass
