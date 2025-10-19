"""
Nightly maintenance: index repo & run policy tests without spawning subprocesses.
This stays compliant with local-only policy (no subprocess, no network).
Run it from a PS7 task that already ran AI-Guard.
"""


def run():
    # 1) Build/refresh the code index
    from ai_lab.indexer import main as index_main  # type: ignore

    index_main()

    # 2) Run policy tests directly via pytest API (quiet)
    import pytest  # type: ignore

    code = pytest.main(["tests/policy", "-q"])
    if code != 0:
        raise SystemExit(code)


if __name__ == "__main__":
    run()
