"""
Example: using AlphaRegistry to register, query, and get latest alphas.
Run with:  python -m docs.example_registry_usage
"""

from pathlib import Path
from src.registry.alpha_registry import AlphaRegistry


def main():
    db = Path("_demo_registry.duckdb")
    reg = AlphaRegistry(db).init()

    print("Registering example alphas ...")
    reg.register("config_A", {"sharpe": 1.1, "ret": 0.14}, ["fx", "m5"])
    reg.register("config_B", {"sharpe": 1.3, "ret": 0.18}, ["fx", "h1"])
    reg.register("config_C", {"sharpe": 0.9, "ret": 0.10}, ["alt"])

    print("\nTop by Sharpe:")
    for row in reg.get_best("sharpe", 2):
        print(row)

    print("\nLatest overall:")
    print(reg.get_latest())

    print("\nLatest FX-tagged:")
    print(reg.get_latest("fx"))


if __name__ == "__main__":
    main()
