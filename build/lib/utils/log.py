# src/utils/log.py
from datetime import datetime


def log(level: str, msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {level.upper():<5} {msg}")
