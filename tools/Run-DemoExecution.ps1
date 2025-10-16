param(
  [string]$Pair = "EURUSD",
  [string]$TF = "H1",
  [string]$Start = "2024-01-01",
  [string]$End   = "2024-01-03",
  [ValidateSet("mr","breakout")]
  [string]$Strategy = "mr"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Py   = Join-Path $Root ".venv/Scripts/python.exe"; if (-not (Test-Path $Py)) { $Py = "python" }

$old = $env:PYTHONPATH
$env:PYTHONPATH = "$Root;$Root\src"

# build python as a temp file (no here-strings, PS7-safe)
$pyLines = @(
  "import sys, os, json",
  "from src.data.dukascopy import BarSpec, get_bars",
  "from src.backtest.api import BacktestEngine",
  "from src.strategies.api import generate_signals",
  "",
  "# argv: script pair tf start end strat",
  "if len(sys.argv) < 6: raise SystemExit('usage: <script> pair tf start end strat')",
  "_, pair, tf, start, end, strat = sys.argv[:6]",
  "spec = BarSpec(pair, tf, start, end)",
  "df = get_bars(spec)",
  "if strat=='mr':",
  "    from src.strategies.mr import MeanReversion as S",
  "elif strat=='breakout':",
  "    from src.strategies.breakout import Breakout as S",
  "else:",
  "    raise SystemExit('unknown strategy: '+strat)",
  "s = S()",
  "sig = generate_signals(s, df)",
  "bt = BacktestEngine(df, sig)",
  "res = bt.run()",
  "",
  "run_key = pair + '_' + tf + '_' + start.replace('-','') + '_' + end.replace('-','')",
  "base = os.path.join('artifacts','backtests', run_key, strat)",
  "os.makedirs(base, exist_ok=True)",
  "e = res.get('equity')",
  "p = res.get('pnl')",
  "if hasattr(e,'to_csv'): e.to_csv(os.path.join(base,'equity.csv'), header=True)",
  "if p is None and hasattr(e,'pct_change'): p = e.pct_change().fillna(0.0)",
  "if hasattr(p,'to_csv'): p.to_csv(os.path.join(base,'pnl.csv'), header=True)",
  "summary={}",
  "try:",
  "    if hasattr(p,'sum'): summary['ret']=float(p.sum())",
  "    if hasattr(p,'std'): summary['vol']=float(p.std()*(252**0.5))",
  "except Exception: pass",
  "with open(os.path.join(base,'summary.json'),'w',encoding='utf-8') as fh: json.dump(summary, fh)",
  "print('packed to ', base)"
)
$tmpPy = Join-Path $env:TEMP ("demo_exec_" + [guid]::NewGuid().ToString("N") + ".py")
[IO.File]::WriteAllLines($tmpPy, $pyLines, (New-Object System.Text.UTF8Encoding($false)))

try {
  & $Py $tmpPy $Pair $TF $Start $End $Strategy
} finally {
  $env:PYTHONPATH = $old
  Remove-Item -LiteralPath $tmpPy -Force -ErrorAction SilentlyContinue
}
