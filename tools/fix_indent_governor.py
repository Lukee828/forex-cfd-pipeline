import io, os, re, sys

def read(p): 
    with io.open(p, "r", encoding="utf-8", newline="") as f: 
        return f.read()

def write(p, s):
    with io.open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)

rg = os.path.join("src","risk","risk_governor.py")
if not os.path.exists(rg):
    print("missing:", rg); sys.exit(1)

s = read(rg)

# --- locate class RiskGovernor header ---
m_class = re.search(r'(?m)^(?P<indent>\s*)class\s+RiskGovernor\b[^\n]*:\s*$', s)
if not m_class:
    print("RiskGovernor class not found"); sys.exit(1)

cls_indent = m_class.group("indent")
meth_indent = cls_indent + "    "  # one level inside class
body_indent = meth_indent + "    " # one level inside method

# --- remove any existing _vol_scale definitions (anywhere) ---
pat_vol = re.compile(r'(?ms)^\s*def\s+_vol_scale\s*\([^)]*\)\s*->\s*Tuple\[[^\]]*\]\s*:\s*.*?(?=^\S|^\s*def\s+|\Z)')
s = pat_vol.sub("", s)

# --- insert the method right AFTER the class header line ---
insert_at = m_class.end()
method = (
    f"{meth_indent}def _vol_scale(self) -> Tuple[float, dict]:\n"
    f"{body_indent}sig_daily = ewma_vol(self._rets, self.cfg.ewma_lambda)\n"
    f"{body_indent}sig_ann = sig_daily * np.sqrt(self.cfg.trading_days)\n"
    f"{body_indent}if sig_ann <= 0:\n"
    f"{body_indent}    return 1.0, {{\"sig_ann\": float(sig_ann)}}\n"
    f"{body_indent}\n"
    f"{body_indent}target = self.cfg.vol_target\n"
    f"{body_indent}floor = self.cfg.vol_floor\n"
    f"{body_indent}ceil = self.cfg.vol_ceiling\n"
    f"{body_indent}raw = target / sig_ann\n"
    f"{body_indent}clamped = float(min(max(raw, floor), ceil))\n"
    f"{body_indent}return clamped, {{\"sig_ann\": float(sig_ann), \"raw\": float(raw), \"clamped\": clamped}}\n"
)

# ensure a blank line before method if next char isn't a newline
prefix = "" if s[insert_at:insert_at+1] == "\n" else "\n"
s2 = s[:insert_at] + prefix + method + s[insert_at:]

write(rg, s2)
print("✓ fixed indentation & placement ->", rg)
