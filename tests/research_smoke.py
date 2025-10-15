from alpha_factory.research.research_loop import run

res = run(["XAUUSD"], "M5", 300, None, None, "data/features", "data/feature_store.duckdb")
print(res)
