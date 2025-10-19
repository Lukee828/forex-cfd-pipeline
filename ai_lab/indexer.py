import ast
import json
from pathlib import Path


def build_index(root: str = "."):
    index = {"modules": {}, "errors": []}
    for f in Path(root).rglob("*.py"):
        if any(p in f.parts for p in (".venv", ".git", "__pycache__")):
            continue
        try:
            src = f.read_text(encoding="utf-8")
            tree = ast.parse(src)
            funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
            classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
            index["modules"][str(f)] = {"funcs": funcs, "classes": classes}
        except Exception as e:
            index["errors"].append([str(f), repr(e)])
    out = Path("ai_lab/index")
    out.mkdir(parents=True, exist_ok=True)
    (out / "structure.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    print("Wrote ai_lab/index/structure.json with", len(index["modules"]), "modules")


if __name__ == "__main__":
    build_index(".")
