import pathlib
import re

P = pathlib.Path(r"src/exec/daily_run.py")
txt = P.read_text(encoding="utf-8")

# 1) capture optional top-level docstring
doc, rest = "", txt
m = re.match(r'^\s*(?P<q>"""|\'\'\')(?P<body>.*?)(?P=q)\s*', txt, flags=re.DOTALL)
if m:
    doc = m.group(0)
    rest = txt[m.end() :]

# 2) pull future-import + normal imports to the top (remove from body)
imports = []
body_lines = []
for line in rest.splitlines():
    if re.match(r"^\s*from __future__ import annotations\s*$", line) or re.match(
        r"^\s*(import|from)\s+\S+", line
    ):
        imports.append(line.rstrip())
    else:
        body_lines.append(line)
body = "\n".join(body_lines).lstrip("\n")

# ensure future import first
future = "from __future__ import annotations"
imports_uniq = []
seen = set()
for x in imports:
    if x not in seen:
        imports_uniq.append(x)
        seen.add(x)
if future in imports_uniq:
    imports_uniq.remove(future)
imports_ordered = [future] + imports_uniq

# 3) pull the shim (if present) out of body and place it *after* imports
shim_pat = re.compile(r"^\s*def\s+_no_subprocess\s*\(.*?\n(?:\s+.*\n)*", re.MULTILINE)
shim = ""
m2 = shim_pat.search(body)
if m2:
    shim = m2.group(0)
    body = body[: m2.start()] + body[m2.end() :]
else:
    # if no shim exists, define it now (policy-safe)
    shim = (
        "def _no_subprocess(*args, **kwargs):\n"
        '    raise RuntimeError("Blocked by local-only policy: subprocess is disabled")\n'
    )

# 4) ensure all call sites use shim
body = re.sub(r"subprocess\.run\s*\(", "_no_subprocess(", body, flags=re.IGNORECASE)

# 5) rebuild file
new_txt = (
    (doc if doc else "")
    + ("\n" if doc and not doc.endswith("\n") else "")
    + "\n".join(imports_ordered).rstrip()
    + "\n\n"
    + shim.rstrip()
    + "\n\n"
    + body.lstrip()
).rstrip("\n") + "\n"

P.write_text(new_txt.replace("\r\n", "\n"), encoding="utf-8")
print("normalized:", P)
