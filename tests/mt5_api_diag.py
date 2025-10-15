import sys, time
import MetaTrader5 as mt5

CANDIDATES = ["C:\\Program Files\\MetaTrader 5 IC Markets EU\\terminal64.exe", "C:\\Program Files\\AMP Global (USA) MT5 Exchange-Traded Futures Only\\terminal64.exe", "C:\\Program Files\\FTMO MetaTrader 5\\terminal64.exe"]

def try_init(path=None):
    if path:
        ok = mt5.initialize(path)
    else:
        ok = mt5.initialize()
    if not ok:
        return False, mt5.last_error()
    return True, None

def main():
    # 1) Try default attach to running terminal
    ok, err = try_init(None)
    if not ok:
        # 2) Try each candidate path
        for p in CANDIDATES:
            ok, err = try_init(p)
            if ok:
                print("INIT_WITH_PATH", p)
                break
    else:
        print("INIT_DEFAULT")

    if not ok:
        print("INIT_FAIL", err)
        return 2

    try:
        print("VERSION", mt5.version())
        ti = mt5.terminal_info()
        print("TERMINAL", ti)
        t = mt5.symbol_info_tick("XAUUSD")
        print("TICK", t)
    finally:
        mt5.shutdown()
    return 0

if __name__ == "__main__":
    sys.exit(main())
