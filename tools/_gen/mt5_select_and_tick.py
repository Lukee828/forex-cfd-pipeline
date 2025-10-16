import sys
import MetaTrader5 as mt5

symbols = sys.argv[1:] or ["XAUUSD", "US30.cash", "GER40.cash"]
if not mt5.initialize():
    print("INIT_FAIL", mt5.last_error())
    sys.exit(2)
try:
    for s in symbols:
        ok = mt5.symbol_select(s, True)
        info = mt5.symbol_info(s)
        tick = mt5.symbol_info_tick(s)
        print(
            f"{s}: selected={ok}, exists={bool(info)}, visible={getattr(info, 'visible', None) if info else None}, tick={tick}"
        )
finally:
    mt5.shutdown()
