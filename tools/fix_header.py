import pathlib
import re

p = pathlib.Path(r"src/alpha_factory/alpha_registry_ext_overrides_024.py")
txt = p.read_text(encoding="utf-8")

# --- 1) Peel off an optional top-level docstring (triple quotes) safely ---
doc = ""
rest = txt
if txt.lstrip().startswith('"""') or txt.lstrip().startswith("'''"):
    start = txt.find('"""' if txt.lstrip().startswith('"""') else "'''", 0)
    q = txt[start : start + 3]
    end = txt.find(q, start + 3)
    if end != -1:
        end += 3
        doc = txt[:end].rstrip() + "\n"
        rest = txt[end:]

# --- 2) Pull imports we want at the very top (remove them from body) ---
wanted = [
    r"^\s*from __future__ import annotations\s*$",
    r"^\s*from weakref import WeakKeyDictionary as _WKD\s*$",
    r"^\s*from typing import .*$",
    r"^\s*import duckdb\s*$",
    r"^\s*import pandas as pd\s*$",
    r"^\s*from registry\.alpha_registry import AlphaRegistry.*$",
]
imports = []
for pat in wanted:
    out = []
    for line in rest.splitlines():
        if re.match(pat, line):
            imports.append(line)
        else:
            out.append(line)
    rest = "\n".join(out)

# de-duplicate while preserving order
seen = set()
imports = [x for x in imports if not (x in seen or seen.add(x))]

# ensure __future__ first (insert if missing)
future = "from __future__ import annotations"
if future not in imports:
    imports.insert(0, future)

# --- 3) Rebuild header: [doc][future+imports][blank][rest] ---
header = (doc if doc else "") + "\n".join(imports) + "\n\n"
new_txt = header + rest.lstrip()

# normalize to LF and write back
p.write_text(new_txt.replace("\r\n", "\n"), encoding="utf-8")
print("fixed:", p)
