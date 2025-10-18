import pathlib
import re

EXCLUDE_PARTS = {".git", "__pycache__"}
EXCLUDE_SUBSTRINGS = {"venv", "Scripts"}  # ignore any venvs & activation scripts


def ps1_files(root=pathlib.Path(".")):
    files = []
    for p in root.rglob("*.ps1"):
        parts = set(p.parts)
        if parts & EXCLUDE_PARTS:
            continue
        joined = str(p).lower()
        if any(s.lower() in joined for s in EXCLUDE_SUBSTRINGS):
            continue
        files.append(p)
    return files


def test_ps_scripts_have_param_block():
    for p in ps1_files():
        txt = p.read_text(encoding="utf-8", errors="ignore")
        assert re.search(
            r"^\s*(?:\[[^\]]+\]\s*)*param\s*\(", txt, re.I | re.M
        ), f"Missing param() in {p}"


def test_ps_scripts_no_read_host():
    for p in ps1_files():
        txt = p.read_text(encoding="utf-8", errors="ignore")
        assert "Read-Host" not in txt, f"Read-Host found in {p}"
