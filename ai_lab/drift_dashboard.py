# Placeholder for drift dashboard
from pathlib import Path


def build():
    out = Path("docs/drift.md")
    out.write_text("# Drift Dashboard\n\n(Coming soon)\n", encoding="utf-8")
    print("Wrote", out)


if __name__ == "__main__":
    build()
