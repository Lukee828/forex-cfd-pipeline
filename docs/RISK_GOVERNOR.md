# Risk governor usage

```python
from src.runtime.governor_integration import governor_scale
scale, info = governor_scale(last_price, account_equity)
qty = base_qty * scale
```

Environment overrides:
- GOV_OFF
- GOV_VOL_TARGET
- GOV_VOL_WINDOW
- GOV_VOL_MIN_SCALE
- GOV_VOL_MAX_SCALE
- GOV_DD_WINDOW
- GOV_MAX_DD
- GOV_DD_FLOOR
- GOV_TRADING_DAYS