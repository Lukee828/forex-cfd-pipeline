from dataclasses import dataclass
from typing import Optional, Dict

@dataclass
class OrderIntent:
    ts_utc: "pd.Timestamp"
    symbol: str
    side: str               # 'long' | 'short' | 'flat'
    entry: Dict             # {'type': 'mkt'|'stop'|'limit', 'price': float|None}
    exit: Optional[Dict]    # {'tp': float|None, 'sl': float|None, 'ttl_bars': int|None}
    tag: str                # sleeve name
    priority: int           # higher wins
    confidence: float       # 0..1
