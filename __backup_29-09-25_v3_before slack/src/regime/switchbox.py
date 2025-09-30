from dataclasses import dataclass
import pandas as pd

@dataclass
class RegimeState:
    date: pd.Timestamp
    label: str
    features: dict

def label_regime(features: pd.DataFrame)->RegimeState:
    # Placeholder: simple vol percentile
    last = features.iloc[-1]
    label = "Calm"
    if last.get("vol_pct", 0) >= 50:
        label = "Expansion"
    if last.get("risk_off", False):
        label = "RiskOff"
    return RegimeState(date=last.name if hasattr(last, 'name') else pd.Timestamp.utcnow(),
                       label=label,
                       features=last.to_dict())

def sleeve_weights(label: str)->dict:
    defaults = {
      "Calm":     {"tsmom":0.6,"xsec":0.6,"mr_vwap":1.2,"orb_nr7":0.8,"seasonality":1.2,"carry":1.0},
      "Expansion":{"tsmom":1.3,"xsec":1.2,"mr_vwap":0.5,"orb_nr7":1.1,"seasonality":0.7,"carry":1.0},
      "RiskOff":  {"tsmom":1.2,"xsec":0.6,"mr_vwap":0.3,"orb_nr7":0.8,"seasonality":0.6,"carry":0.5},
    }
    return defaults.get(label, defaults["Calm"])
