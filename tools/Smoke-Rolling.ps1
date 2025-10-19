param()
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."

# --- Numpy path ---
$code = @"
import numpy as np
from src.utils.rolling import roll_mean

x = np.arange(1, 101, dtype=float)
y = roll_mean(x, 20)
assert np.isnan(y[:19]).all() and np.isfinite(y[19:]).all()
print("ROLL numpy OK")
"@
$code | & $py -

# --- Numba path (falls back if numba absent) ---
$code2 = @"
import os, numpy as np
os.environ["ROLL_IMPL"] = "numba"
from src.utils.rolling import roll_mean

x = np.arange(1, 101, dtype=float)
y = roll_mean(x, 20)
assert np.isnan(y[:19]).all()
print("ROLL numba OK (or fallback)")
"@
$code2 | & $py -
