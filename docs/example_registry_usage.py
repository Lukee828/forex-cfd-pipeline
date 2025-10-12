# Example usage (explicitly install v0.2.4 overrides first)

# Import the overrides module: this monkey-patches AlphaRegistry on import
import alpha_factory.alpha_registry_ext_overrides_024  # noqa: F401

from alpha_factory.alpha_registry import AlphaRegistry
from alpha_factory.drift_dashboard import plot_alpha_performance

# Smart constructor that adapts to your AlphaRegistry signature
import inspect


def _new_registry(db_path="data/registry.duckdb"):
    sig = inspect.signature(AlphaRegistry.__init__)
    params = sig.parameters
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
    # Ensure internal path points to db_path if such attribute exists
    for attr in ("db_path", "path", "database"):
        if hasattr(reg, attr):
            try:
                setattr(reg, attr, str(db_path))
            except Exception:
                pass
    return reg


reg = _new_registry()

# 1) Rank & summary
try:
    ranked = reg.rank(metric="sharpe", top_n=10)
    print("RANKED\\n", ranked.head() if hasattr(ranked, "head") else ranked)
except Exception as e:
    print("rank() failed:", e)

try:
    summary = reg.get_summary(metric="sharpe")
    print("SUMMARY\\n", summary.head() if hasattr(summary, "head") else summary)
except Exception as e:
    print("get_summary() failed:", e)

# 2) Compare
try:
    wide = reg.compare(["s2e_brk", "xsmom", "tf_mr_combo"], metric="sharpe")
    print("COMPARE\\n", wide)
except Exception as e:
    print("compare() failed:", e)

# 3) Lineage
try:
    lin = reg.get_lineage("s2e_brk")
    print("LINEAGE\\n", lin.head() if hasattr(lin, "head") else lin)
except Exception as e:
    print("get_lineage() failed:", e)

# 4) Dashboard
try:
    if "ranked" in locals() and hasattr(ranked, "empty") and not ranked.empty:
        png = plot_alpha_performance(
            ranked[["alpha_id", "value"]], title="Top by Sharpe"
        )
        print("Saved dashboard to:", png)
except Exception as e:
    print("dashboard failed:", e)
