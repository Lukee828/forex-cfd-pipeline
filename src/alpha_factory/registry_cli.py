# src/alpha_factory/registry_cli.py — shim so tests can run: python -m alpha_factory.registry_cli ...
from importlib import import_module

CANDIDATES = [
    ("alpha_factory.registry_tooling_v027", "main"),
    ("alpha_factory.registry_tooling_v028", "main"),
    ("alpha_factory.registry_tooling", "main"),
]


def _resolve():
    for mod_name, func_name in CANDIDATES:
        try:
            mod = import_module(mod_name)
            fn = getattr(mod, func_name, None)
            if callable(fn):
                return fn
        except Exception:
            continue
    raise SystemExit(
        "registry_cli shim: no backend found among: " + ", ".join(m for m, _ in CANDIDATES)
    )


def main() -> int:
    fn = _resolve()
    return int(fn())


if __name__ == "__main__":
    raise SystemExit(main())
