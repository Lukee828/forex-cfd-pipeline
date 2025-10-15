import sys
import MetaTrader5 as mt5

symbols = sys.argv[1:] or ["XAUUSD", "US30", "DE40"]
if not mt5.initialize():
    print("INIT_FAIL", mt5.last_error())
    sys.exit(2)
try:
    for s in symbols:
        mt5.symbol_select(s, True)
        t = mt5.symbol_info_tick(s)
        print(f"{s} -> {t}")
finally:
    mt5.shutdown()
