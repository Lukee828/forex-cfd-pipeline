from pathlib import Path
import re


def _strip_comments_and_strings(text: str) -> str:
    # Remove PowerShell line comments
    text = re.sub(r"(?m)^\s*#.*$", "", text)
    # Remove single- and double-quoted strings
    text = re.sub(r'"(?:[^"\\]|\\.)*"', '""', text)
    text = re.sub(r"'(?:[^'\\]|\\.)*'", "''", text)
    return text


def test_ai_guard_present_and_noninteractive():
    p = Path("tools/AI-Guard.ps1")
    assert p.exists(), "AI-Guard.ps1 missing"
    s = p.read_text(encoding="utf-8")

    # Still sanity-check expected sections exist
    assert 'Head "PS7 policy checks"' in s
    assert 'Head "Python banned-call scan"' in s

    # No *executable* Read-Host usage (allow mentions inside strings/comments)
    code = _strip_comments_and_strings(s)
    assert re.search(r"\bRead-Host\b", code) is None, "interactive Read-Host found in code"
