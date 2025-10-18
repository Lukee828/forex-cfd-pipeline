import pathlib
import re

ROOT = pathlib.Path("src/exec")


def fix_file(p: pathlib.Path):
    txt = p.read_text(encoding="utf-8")

    # 0) Split out optional module docstring
    doc = ""
    rest = txt
    m = re.match(r'^\s*(?P<q>"""|\'\'\')(?P<body>.*?)(?P=q)\s*', txt, flags=re.DOTALL)
    if m:
        doc = m.group(0)
        rest = txt[m.end() :]

    # 1) Scan lines; collect ONLY top-level imports (col-0), including multiline blocks
    lines = rest.splitlines()
    imports_blocks = []
    body_idx = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        if re.match(r"^(from\s+\S+\s+import\s+.*|import\s+\S+)", line):
            block = [line]
            parens = line.count("(") - line.count(")")
            # capture parenthesized block
            j = i + 1
            while parens > 0 and j < len(lines):
                block.append(lines[j])
                parens += lines[j].count("(") - lines[j].count(")")
                j += 1
            imports_blocks.append(block)
            i = j
        else:
            # stop scanning imports at the first non-import top-level stmt
            body_idx = i
            break
    if body_idx == 0 and not imports_blocks:
        # no imports at top, leave body as-is
        body_lines = lines
    else:
        body_lines = lines[body_idx:]

    # 2) If we captured a "from ... import (" block header but its closing/group lines
    #    got stranded in the body, try to reattach them.
    def reattach_multiline_names(header_block, body_lines):
        """If header ends with 'import (' and body has a trailing list of names ending with ')',
        pull that contiguous name block up and remove from body."""
        hdr = header_block[0]
        if not hdr.rstrip().endswith("("):
            return header_block, body_lines
        # look for a contiguous name list: lines like '    Name,' and then a line with ')'
        start = None
        for idx, bl in enumerate(body_lines):
            if re.match(r"^\s*[A-Za-z_]\w*(\.[A-Za-z_]\w*)?,\s*$", bl):
                start = idx
                break
        if start is None:
            return header_block, body_lines
        end = start
        saw_close = False
        while end < len(body_lines):
            s = body_lines[end]
            if re.match(r"^\s*\)\s*$", s):
                saw_close = True
                end += 1
                break
            if not re.match(r"^\s*[A-Za-z_]\w*(\.[A-Za-z_]\w*)?,\s*$", s):
                # not a pure name line; abort
                start = None
                break
            end += 1
        if start is not None and saw_close:
            block = header_block[:] + body_lines[start:end]
            body_lines = body_lines[:start] + body_lines[end:]
            return block, body_lines
        return header_block, body_lines

    new_import_blocks = []
    for blk in imports_blocks:
        blk2, body_lines = reattach_multiline_names(blk, body_lines)
        new_import_blocks.append(blk2)
    imports_blocks = new_import_blocks

    # 3) Build import text; ensure future import first, drop duplicate blocks
    import_texts = ["\n".join(b).rstrip() for b in imports_blocks]
    # flatten and dedupe while preserving order
    seen = set()
    flat = []
    for t in import_texts:
        if t not in seen:
            seen.add(t)
            flat.append(t)
    # ensure future import first (remove if present and re-add at top)
    future = "from __future__ import annotations"
    has_future = any(
        re.match(r"^\s*from __future__ import annotations\s*$", line)
        for t in flat
        for line in t.splitlines()
    )
    flat = [t for t in flat if not re.match(r"^\s*from __future__ import annotations\s*$", t)]
    if has_future:
        flat = [future] + flat
    imports_text = ("\n".join(flat).rstrip() + "\n\n") if flat else ""

    # 4) Body: do NOT move indented imports (inside try/except); just clean subprocess usage
    body = "\n".join(body_lines)

    # Remove any top-level 'import subprocess' that slipped into body accidentally (col-0 only)
    body = re.sub(r"(?m)^(import\s+subprocess\s*)\n", "", body)

    # Replace subprocess.run/call with shim
    body = re.sub(r"\bsubprocess\.run\s*\(", "_no_subprocess(", body)
    body = re.sub(r"\bsubprocess\.call\s*\(", "_no_subprocess(", body)

    # 5) Shim (once), placed after imports
    shim = (
        "def _no_subprocess(*args, **kwargs):\n"
        '    raise RuntimeError("Blocked by local-only policy: subprocess is disabled")\n'
    )

    # 6) Reassemble
    new_txt = (
        (doc if doc else "")
        + ("" if not doc else ("\n" if not doc.endswith("\n") else ""))
        + imports_text
        + shim
        + "\n"
        + body.lstrip()
    )
    new_txt = new_txt.replace("\r\n", "\n").rstrip("\n") + "\n"
    p.write_text(new_txt, encoding="utf-8")
    print("fixed:", p)


for p in sorted(ROOT.glob("*.py")):
    if p.name == "__init__.py":
        continue
    fix_file(p)
