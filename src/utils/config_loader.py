import os
import re
import yaml

_pattern = re.compile(r".*?\${(\w+)}.*?")


def _replace_env_vars(obj):
    """Recursively replace ${VAR} with os.environ['VAR'] if present."""
    if isinstance(obj, str):
        matches = _pattern.findall(obj)
        for m in matches:
            val = os.environ.get(m, f"${{{m}}}")  # leave as-is if not found
            obj = obj.replace(f"${{{m}}}", val)
        return obj
    elif isinstance(obj, list):
        return [_replace_env_vars(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: _replace_env_vars(v) for k, v in obj.items()}
    else:
        return obj


def load_yaml_with_env(path):
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return _replace_env_vars(raw)
