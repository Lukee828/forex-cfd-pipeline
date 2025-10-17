import io, os, re, sys
ROOT = os.path.abspath(os.getcwd())

def read(p): 
    with io.open(p, "r", encoding="utf-8", newline="") as f: 
        return f.read()

def write(p, s):
    with io.open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)

# ---------- 1) Canonicalize export_features.py header ----------
exp = os.path.join("src","infra","export_features.py")
if os.path.exists(exp):
    s = read(exp)
    # keep everything from the first @dataclass downward
    m = re.search(r'(?m)^\s*@dataclass\b', s)
    tail = s[m.start():] if m else s
    header = """# Optional imports; keep soft so local dev never breaks.
try:
    from src.risk.spread_guard import SpreadGuardConfig, check_spread_ok  # type: ignore
except Exception:  # pragma: no cover - optional
    SpreadGuardConfig = None  # type: ignore
    check_spread_ok = None  # type: ignore

from ._compat_risk import new_spread_guard_config

try:
    from src.risk.vol_state import VolStateMachine, infer_vol_regime  # type: ignore
except Exception:  # pragma: no cover - optional
    VolStateMachine = None  # type: ignore
    infer_vol_regime = None  # type: ignore

"""
    fixed = header + tail
    write(exp, fixed)
    print(f"✓ fixed header -> {exp}")
else:
    print(f"• skip (missing): {exp}")

# ---------- 2) Repair RiskGovernor._vol_scale ----------
rg = os.path.join("src","risk","risk_governor.py")
if os.path.exists(rg):
    s = read(rg)

    # ensure Tuple import
    if not re.search(r'(?m)^\s*from\s+typing\s+import\s+.*\bTuple\b', s):
        if re.search(r'(?m)^\s*from\s+typing\s+import\s+', s):
            s = re.sub(r'(?m)^(from\s+typing\s+import\s+)([^\n]+)$',
                       lambda m: m.group(1)+m.group(2)+", Tuple" if "Tuple" not in m.group(2) else m.group(0),
                       s, count=1)
        else:
            # insert near top, after any future-imports if present
            s = re.sub(r'(?m)^(from __future__.*\n)+', lambda m: m.group(0)+"from typing import Tuple\n", s, count=1)
            if "from typing import Tuple" not in s:
                s = "from typing import Tuple\n" + s

    block = (
        "    def _vol_scale(self) -> Tuple[float, dict]:\n"
        "        sig_daily = ewma_vol(self._rets, self.cfg.ewma_lambda)\n"
        "        sig_ann = sig_daily * np.sqrt(self.cfg.trading_days)\n"
        "        if sig_ann <= 0:\n"
        "            return 1.0, {\"sig_ann\": float(sig_ann)}\n"
        "\n"
        "        target = self.cfg.vol_target\n"
        "        floor = self.cfg.vol_floor\n"
        "        ceil = self.cfg.vol_ceiling\n"
        "        raw = target / sig_ann\n"
        "        clamped = float(min(max(raw, floor), ceil))\n"
        "        return clamped, {\"sig_ann\": float(sig_ann), \"raw\": float(raw), \"clamped\": clamped}\n"
    )

    # replace existing method or insert after class header
    pat = re.compile(r'(?ms)^\s*def\s+_vol_scale\s*\(.*?\):.*?(?=^\s*def\s+\w+\s*\(|^\S|\Z)')
    if pat.search(s):
        s = pat.sub(block, s, count=1)
    else:
        s = re.sub(r'(?m)^(class\s+RiskGovernor[^\n]*:\s*\n)', r"\1"+block, s, count=1)

    write(rg, s)
    print(f"✓ repaired _vol_scale -> {rg}")
else:
    print(f"• skip (missing): {rg}")
