import sys
import MetaTrader5 as mt5

if not mt5.initialize():
    print("INIT_FAIL", mt5.last_error())
    sys.exit(2)
try:
    print("VERSION", mt5.version())
    print("TERMINAL", mt5.terminal_info())
    print("ACCOUNT", mt5.account_info())
finally:
    mt5.shutdown()
