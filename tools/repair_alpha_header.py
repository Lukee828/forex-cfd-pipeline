import pathlib
import re

P = pathlib.Path(r"src/alpha_factory/alpha_registry_ext_overrides_024.py")
txt = P.read_text(encoding="utf-8")

# optional top-level docstring
doc = ""
rest = txt
s = txt.lstrip()
if s.startswith('"""') or s.startswith("'''"):
    q = '"""' if s.startswith('"""') else "'''"
    start = txt.find(q)
    end = txt.find(q, start + 3)
    if end != -1:
        end += 3
        doc = txt[:end].rstrip() + "\n"
        rest = txt[end:]

# drop any stray imports of these lines from the body
wanted = [
    r"^\s*from __future__ import annotations\s*$",
    r"^\s*from weakref import WeakKeyDictionary as _WKD\s*$",
    r"^\s*from typing import .*$",  # keep full typing line
    r"^\s*import duckdb\s*$",
    r"^\s*import pandas as pd\s*$",
    r"^\s*from registry\.alpha_registry import AlphaRegistry.*$",
]
body_lines = []
imports_seen = set()
for line in rest.splitlines():
    if any(re.match(p, line) for p in wanted):
        # skip (remove duplicates if they reappear)
        imports_seen.add(line.strip())
        continue
    body_lines.append(line)
rest = "\n".join(body_lines).lstrip()

# canonical header (order fixed; add typing after future)
header_lines = [
    "from __future__ import annotations",
    "from weakref import WeakKeyDictionary as _WKD",
    "from typing import Any, Dict, Optional",
    "import duckdb",
    "import pandas as pd",
    "from registry.alpha_registry import AlphaRegistry  # type: ignore",
]
header = (doc if doc else "") + "\n".join(header_lines) + "\n\n"
new_txt = (header + rest).rstrip("\n") + "\n"

P.write_text(new_txt.replace("\r\n", "\n"), encoding="utf-8")
print("repaired:", P)
