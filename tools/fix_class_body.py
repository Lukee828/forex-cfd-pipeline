import io, os, re, sys

def read(p):
    with io.open(p, "r", encoding="utf-8", newline="") as f:
        return f.read()

def write(p, s):
    with io.open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)

p = os.path.join("src","risk","risk_governor.py")
if not os.path.exists(p):
    print("missing:", p); sys.exit(1)

s = read(p)

# find class RiskGovernor
m = re.search(r'(?m)^(?P<indent>\s*)class\s+RiskGovernor\b[^\n]*:\s*$', s)
if not m:
    print("RiskGovernor class not found"); sys.exit(1)

cls_indent = m.group("indent")
meth_indent = cls_indent + "    "
body_indent = meth_indent + "    "
insert_at = m.end()

# ensure there is at least one indented statement after class header
after = s[insert_at:]
# next non-empty, non-newline token
m_next_line = re.search(r'(?m)^(?P<line>.*)$', after)
need_pass = False
if m_next_line:
    first_line = m_next_line.group("line")
    # if first line is empty OR does not start with more indent than class indent, we need a pass
    if (first_line.strip() == "") or (not first_line.startswith(cls_indent + "    ")):
        need_pass = True
else:
    need_pass = True

# remove ANY stray _vol_scale definitions (anywhere)
s = re.sub(r'(?ms)^\s*def\s+_vol_scale\s*\([^)]*\)\s*->\s*Tuple\[[^\]]*\]\s*:\s*.*?(?=^\S|^\s*def\s+|\Z)', "", s)

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

# Build insertion string (optional pass, then method)
block = ""
if need_pass:
    block += f"{meth_indent}pass\n"
# always add a blank line before method for readability
block += f"\n{method}"

# Insert block right after the class header
prefix = "" if s[insert_at:insert_at+1] == "\n" else "\n"
s2 = s[:insert_at] + prefix + block + s[insert_at:]

write(p, s2)
print("✓ ensured class body & _vol_scale inside class ->", p)
