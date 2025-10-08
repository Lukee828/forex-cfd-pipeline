# Auto-add repository ./src to import path for tests & CI
import sys
import pathlib

root = pathlib.Path(__file__).resolve().parents[1]
src = root / "src"
if src.is_dir():
    p = str(src)
    if p not in sys.path:
        sys.path.insert(0, p)
