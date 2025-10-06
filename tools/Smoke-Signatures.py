import inspect
import sys
from src.risk.time_stop import is_time_stop
from src.risk.overlay import RiskOverlay

ok = True

sig_ts = str(inspect.signature(is_time_stop))
if "bars_elapsed" not in sig_ts or "days_elapsed" not in sig_ts or "cfg" not in sig_ts:
    print("signature drift: is_time_stop", sig_ts)
    ok = False

sig_ro = str(inspect.signature(RiskOverlay.__init__))
for needed in ("spread_fn", "time_stop_fn", "breakeven_fn"):
    if needed not in sig_ro:
        print("signature drift: RiskOverlay.__init__", sig_ro)
        ok = False

sys.exit(0 if ok else 1)
