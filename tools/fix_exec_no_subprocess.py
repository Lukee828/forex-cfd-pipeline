import pathlib
import re

ROOT = pathlib.Path("src/exec")
FILES = [p for p in ROOT.glob("*.py") if p.is_file()]


def normalize(path: pathlib.Path):
    txt = path.read_text(encoding="utf-8")

    # 0) drop any "import subprocess"
    txt = re.sub(r"(?m)^\s*import\s+subprocess\s*\r?\n", "", txt)

    # 1) capture optional top-level docstring
    doc, rest = "", txt
    m = re.match(r'^\s*(?P<q>"""|\'\'\')(?P<body>.*?)(?P=q)\s*', txt, flags=re.DOTALL)
    if m:
        doc = m.group(0)
        rest = txt[m.end() :]

    # 2) lift future+imports
    imports, body_lines = [], []
    for line in rest.splitlines():
        if re.match(r"^\s*from __future__ import annotations\s*$", line) or re.match(
            r"^\s*(import|from)\s+\S+", line
        ):
            imports.append(line.rstrip())
        else:
            body_lines.append(line)
    body = "\n".join(body_lines).lstrip("\n")

    # 3) ensure future first, dedupe
    future = "from __future__ import annotations"
    uniq, seen = [], set()
    for x in imports:
        if x not in seen:
            uniq.append(x)
            seen.add(x)
    if future in uniq:
        uniq.remove(future)
    imports = [future] + uniq

    # 4) extract or define shim, then place after imports
    shim_pat = re.compile(r"^\s*def\s+_no_subprocess\s*\(.*?\n(?:\s+.*\n)*", re.MULTILINE)
    m2 = shim_pat.search(body)
    if m2:
        shim = m2.group(0)
        body = body[: m2.start()] + body[m2.end() :]
    else:
        shim = (
            "def _no_subprocess(*args, **kwargs):\n"
            '    raise RuntimeError("Blocked by local-only policy: subprocess is disabled")\n'
        )

    # 5) replace all call sites
    body = re.sub(r"subprocess\.run\s*\(", "_no_subprocess(", body, flags=re.IGNORECASE)

    new_txt = (
        (doc if doc else "")
        + ("\n" if doc and not doc.endswith("\n") else "")
        + "\n".join(imports).rstrip()
        + "\n\n"
        + shim.rstrip()
        + "\n\n"
        + body.lstrip()
    ).rstrip("\n") + "\n"

    path.write_text(new_txt.replace("\r\n", "\n"), encoding="utf-8")
    print("fixed:", path)


for p in FILES:
    normalize(p)
