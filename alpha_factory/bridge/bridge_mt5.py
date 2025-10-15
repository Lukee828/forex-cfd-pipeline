from __future__ import annotations
import argparse
import json
import socket
import sys
import threading
from pathlib import Path

DEFAULT_CFG = {
    "host": "127.0.0.1",
    "port": 5005,
    "allowed_symbols": ["XAUUSD", "US30.cash", "GER40.cash"],
    "risk_guard": {"enabled": True},
}


def load_config(p):
    if not p:
        return DEFAULT_CFG.copy()
    t = Path(p)
    if not t.exists():
        print(f"[bridge] Config not found: {t} -> defaults", file=sys.stderr)
        return DEFAULT_CFG.copy()
    try:
        cfg = json.loads(t.read_text(encoding="utf-8").strip())
        out = DEFAULT_CFG.copy()
        out.update(cfg)
        return out
    except json.JSONDecodeError as e:
        print(f"[bridge] Config parse failed: {e}", file=sys.stderr)
        return DEFAULT_CFG.copy()


def _recv_line(c, timeout=10.0):
    c.settimeout(timeout)
    b = bytearray()
    try:
        while True:
            x = c.recv(1)
            if not x:
                break
            if x == b"\n":
                break
            b.extend(x)
        if not b and not x:
            return None
        return b.decode("utf-8", "replace").strip()
    except Exception:
        return None


def _send_line(c, s):
    c.sendall((s + "\n").encode("utf-8"))


def handle_client(conn, addr, cfg):
    try:
        _send_line(conn, "HELLO MT5-BRIDGE")
        while True:
            line = _recv_line(conn)
            if line is None:
                break
            u = line.upper()
            if u == "PING":
                _send_line(conn, "PONG")
            elif u == "SYMBOLS":
                _send_line(conn, ",".join(cfg["allowed_symbols"]))
            elif u.startswith("ECHO "):
                _send_line(conn, line[5:])
            elif u == "QUIT":
                _send_line(conn, "BYE")
                break
            else:
                _send_line(conn, "ERR unknown")
    finally:
        try:
            conn.close()
        except:
            pass


def serve(cfg_path):
    cfg = load_config(cfg_path)
    host = cfg["host"]
    port = int(cfg["port"])
    print(f"[bridge] Serving on {host}:{port} (allowed={cfg['allowed_symbols']})")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((host, port))
    s.listen(8)
    try:
        while True:
            c, addr = s.accept()
            threading.Thread(target=handle_client, args=(c, addr, cfg), daemon=True).start()
    finally:
        s.close()


def client_ping(cfg_path):
    cfg = load_config(cfg_path)
    with socket.create_connection((cfg["host"], int(cfg["port"])), timeout=3.0) as c:
        _ = _recv_line(c, timeout=1.0)  # discard banner
        _send_line(c, "PING")
        print(_recv_line(c, timeout=3.0) or "")


def client_symbols(cfg_path):
    cfg = load_config(cfg_path)
    with socket.create_connection((cfg["host"], int(cfg["port"])), timeout=3.0) as c:
        _ = _recv_line(c, timeout=1.0)  # discard banner
        _send_line(c, "SYMBOLS")
        print(_recv_line(c, timeout=3.0) or "")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--config", default="configs/bridge_mt5.yaml")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--serve", action="store_true")
    g.add_argument("--ping", action="store_true")
    g.add_argument("--symbols", action="store_true")
    a = ap.parse_args(argv)
    if a.serve:
        serve(a.config)
    elif a.ping:
        client_ping(a.config)
    elif a.symbols:
        client_symbols(a.config)


if __name__ == "__main__":
    import sys

    sys.exit(main())
