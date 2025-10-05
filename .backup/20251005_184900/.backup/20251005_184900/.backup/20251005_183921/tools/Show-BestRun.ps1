param(
  # Optional: point to a specific grid folder. If omitted, uses the most recent runs\ma_grid_* directory.
  [string]$GridPath
)

$ErrorActionPreference = 'Stop'
$py = ".\.venv\Scripts\python.exe"

function Get-LatestGrid {
  param([string]$Path)
  if ($Path -and (Test-Path $Path)) { return (Get-Item $Path).FullName }
  $g = Get-ChildItem runs -Directory -Filter "ma_grid_*" |
       Sort-Object LastWriteTime -Desc | Select-Object -First 1
  if (-not $g) { throw "No runs\ma_grid_* directories found." }
  return $g.FullName
}

# 1) Locate grid + summary
$grid = Get-LatestGrid -Path $GridPath
$summary = Join-Path $grid 'summary.csv'
if (-not (Test-Path $summary)) { throw "Missing summary.csv at $summary. Re-run Summarize-Grid first." }

# 2) Pick best by Sharpe (safely coerce “1,23” → 1.23)
$rows = Import-Csv $summary | ForEach-Object {
  $_ | Add-Member -PassThru NoteProperty SharpeNum (
    [double](($_.Sharpe -replace ',','.') )
  )
}
$best = $rows | Sort-Object SharpeNum -Desc | Select-Object -First 1
if (-not $best) { throw "No rows in summary.csv." }

$runDir = $best.Path
$eqCsv  = Join-Path $runDir 'equity.csv'
if (-not (Test-Path $eqCsv)) { throw "Equity file not found: $eqCsv" }

Write-Host "Best run: fast=$($best.fast) slow=$($best.slow)" -ForegroundColor Cyan
Write-Host "Equity:  $eqCsv" -ForegroundColor DarkCyan

# 3) Call Python to compute stats & save a plot PNG
$code = @"
import sys, os, math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

eq_path = sys.argv[1]
out_dir = os.path.dirname(eq_path)
png_out = os.path.join(out_dir, "equity_plot.png")

# load
df = pd.read_csv(eq_path, parse_dates=[0], index_col=0)
s = df.iloc[:,0].astype(float).replace([np.inf,-np.inf], np.nan).ffill().bfill()

# infer periods/year from median time gap
if len(s.index) >= 2:
    dt = np.median(np.diff(s.index.values).astype("timedelta64[s]").astype(np.int64))
    dt = max(int(dt), 1)
else:
    dt = 24*3600
ppy = (365.25*24*3600) / dt

# log-returns, annualized stats
lr = np.log(s / s.shift(1)).replace([np.inf,-np.inf], np.nan).dropna()
vol_ann = float(lr.std(ddof=0) * math.sqrt(ppy)) if len(lr) else float("nan")
mu_ann  = float(lr.mean() * ppy) if len(lr) else float("nan")
sharpe  = (mu_ann/vol_ann) if (vol_ann and vol_ann > 1e-12) else float("nan")

# CAGR
years = max(1e-9, (s.index[-1] - s.index[0]).days / 365.25)
cagr = (float(s.iloc[-1]) / float(s.iloc[0]))**(1/years) - 1.0 if (years > 0 and s.iloc[0] > 0) else float("nan")

# Max drawdown
roll_max = s.cummax()
dd = s / roll_max - 1.0
maxdd = float(dd.min()) if len(dd) else float("nan")

# Plot
fig = plt.figure(figsize=(10,6))
ax1 = fig.add_subplot(2,1,1)
ax1.plot(s.index, s.values, label="Equity")
ax1.set_title("Equity Curve")
ax1.grid(True, alpha=0.3)
ax1.legend(loc="best")

ax2 = fig.add_subplot(2,1,2, sharex=ax1)
ax2.plot(dd.index, dd.values, label="Drawdown")
ax2.set_title("Drawdown")
ax2.grid(True, alpha=0.3)
ax2.legend(loc="best")

fig.tight_layout()
fig.savefig(png_out, dpi=120)

print(f"PNG: {png_out}")
print(f"bars={len(s)}  Sharpe={sharpe:.2f}  CAGR={cagr*100:.2f}%  Vol={vol_ann*100:.2f}%  MaxDD={maxdd*100:.2f}%")
"@

$out = & $py -c $code $eqCsv 2>&1
$out | ForEach-Object { $_ }   # echo python output

# Optionally open the PNG
$png = Join-Path $runDir 'equity_plot.png'
if (Test-Path $png) {
  Write-Host "Opening plot: $png" -ForegroundColor Green
  Start-Process $png
}
