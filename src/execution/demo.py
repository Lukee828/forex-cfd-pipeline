from __future__ import annotations
import csv, os, time
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class DemoBroker:
    def __post_init__(self):
        os.makedirs("artifacts", exist_ok=True)
        self.path = os.path.join("artifacts", f"orders-{int(time.time())}.csv")
        with open(self.path,"w",newline="") as f:
            csv.writer(f).writerow(["ts","pair","side","qty","price"])
    def send(self, pair: str, side: str, qty: float, price: float) -> Dict[str,Any]:
        with open(self.path,"a",newline="") as f:
            csv.writer(f).writerow([int(time.time()), pair, side, qty, price])
        return {"ok": True, "path": self.path}
