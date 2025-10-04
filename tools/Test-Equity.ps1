param([string]$RunPath)
$csv = Join-Path $RunPath 'equity.csv'
if (-not (Test-Path $csv)) { $csv = Join-Path $RunPath 'returns.csv' }
if (-not (Test-Path $csv)) { throw "No equity/returns csv in $RunPath" }

$py = ".\.venv\Scripts\python.exe"
$code = @"
import sys, pandas as pd, numpy as np
p = sys.argv[1]
s = pd.read_csv(p, parse_dates=[0], index_col=0).iloc[:,0].astype(float)
s = s.replace([np.inf,-np.inf], np.nan)
n = s.shape[0]
valid = s.dropna()
floor = 1e-6*float(valid.iloc[0]) if len(valid) else 1e-8
floor = max(1e-8, floor)
on_floor = (s <= floor).sum()
print(f"file={p}")
print(f"bars={n}  nan={s.isna().sum()}  floor≈{floor:.3e}  on_floor={on_floor} ({on_floor/max(1,n):.1%})")
print(f"eq_min={s.min():.3e}  eq_p1={valid.quantile(0.01) if len(valid) else np.nan:.6f}  eq_med={valid.median() if len(valid) else np.nan:.6f}  eq_max={s.max():.6f}")
"@
& $py -c $code $csv
