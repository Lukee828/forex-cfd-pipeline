import alpha_factory.alpha_registry_ext_overrides_024  # noqa:F401
from alpha_factory.alpha_registry import AlphaRegistry
from alpha_factory.registry_tooling_v027 import (
    alerts,
    import_csv_to_alphas,
    html_report,
)


def _reg(path):
    try:
        return AlphaRegistry(db_path=path)
    except TypeError:
        return AlphaRegistry(path=path)


def test_alerts_and_report(tmp_path):
    db = tmp_path / "r.duckdb"
    reg = _reg(str(db))
    # seed
    try:
        reg.register("h1", {"sharpe": 1.8}, ["demo"])
        reg.register("h2", {"sharpe": 2.3}, ["demo"])
    except TypeError:
        reg.register(config_hash="h1", metrics={"sharpe": 1.8}, tags=["demo"])
        reg.register(config_hash="h2", metrics={"sharpe": 2.3}, tags=["demo"])

    a = alerts(reg, metric="sharpe", min_value=2.0, tag="demo")
    assert hasattr(a, "shape")

    out = html_report(reg, metric="sharpe", out_html=str(tmp_path / "report.html"))
    assert out.endswith(".html")


def test_csv_import(tmp_path, tmp_path_factory):
    import csv
    import json

    db = tmp_path / "r.duckdb"
    reg = _reg(str(db))
    p = tmp_path / "rows.csv"
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["config_hash", "metrics", "tags"])
        w.writeheader()
        w.writerow({"config_hash": "h3", "metrics": json.dumps({"sharpe": 1.1}), "tags": "csv"})
        w.writerow({"config_hash": "h4", "metrics": json.dumps({"sharpe": 2.5}), "tags": "csv"})
    n = import_csv_to_alphas(reg, str(p))
    assert n == 2
