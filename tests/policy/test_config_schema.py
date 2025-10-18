import jsonschema
import yaml
import pathlib

SCHEMA = {
    "type": "object",
    "properties": {
        "version": {"type": "integer"},
        "updated": {"type": "string"},
        "items": {"type": "array"},
    },
    "required": ["version", "updated", "items"],
}


def test_plan_yaml_schema():
    p = pathlib.Path("ai_lab/plan.yaml")
    assert p.exists(), "ai_lab/plan.yaml missing"
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    jsonschema.validate(data, SCHEMA)
