import sys
import re
import MetaTrader5 as mt5

if not mt5.initialize():
    print("INIT_FAIL", mt5.last_error())
    sys.exit(2)
try:
    pats = {
        "US30": [r"US30", r"\bDJ30\b", r"\bDJI\b", r"Dow"],
        "GER40": [r"GER40", r"\bDE40\b", r"\bDAX\b", r"Germany 40"],
    }
    all_syms = mt5.symbols_get() or []
    print("TOTAL_SYMBOLS", len(all_syms))
    for key, rxlist in pats.items():
        print("\n--- Candidates for", key, "---")
        seen = set()
        for sym in all_syms:
            s = sym.name
            for rx in rxlist:
                if re.search(rx, s, re.IGNORECASE):
                    if s not in seen:
                        seen.add(s)
                        print(s)
                    break
finally:
    mt5.shutdown()
