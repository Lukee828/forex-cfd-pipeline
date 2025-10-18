import yaml
import pathlib


def test_policy_consistency():
    p = pathlib.Path("policy.yaml")
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert data["python"]["version"] == "3.11"
    assert data["network"]["no_network"] is True
    assert "Read-Host" in data["powershell"]["forbidden_cmdlets"]
