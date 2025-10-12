param(
  [string]$Python = ".\.venv311\Scripts\python.exe"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
function Info($m){ Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "[OK]   $m" -ForegroundColor Green }

if (-not (Test-Path $Python)) { throw "Python not found at: $Python" }

$env:PYTHONPATH = (Resolve-Path .\src).Path
$env:MPLBACKEND  = "Agg"

$py = @"
from pathlib import Path
import inspect, duckdb, json
from alpha_factory.alpha_registry import AlphaRegistry
import alpha_factory.alpha_registry_ext_overrides_024 as _ovr  # patches rank/summary/etc.

db = Path("data/registry_v027.duckdb")
db.parent.mkdir(parents=True, exist_ok=True)

# 1) Ensure baseline table (TEXT metrics) and a compatible 'runs' view (metrics->JSON)
con = duckdb.connect(str(db))
con.execute("""
CREATE TABLE IF NOT EXISTS alphas(
  id BIGINT,
  ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  config_hash TEXT,
  metrics TEXT,
  tags TEXT,
  timestamp TIMESTAMP
);
""")
con.execute("""
CREATE OR REPLACE VIEW runs AS
SELECT
  CAST(config_hash AS VARCHAR) AS alpha_id,
  CAST(id AS VARCHAR)          AS run_id,
  COALESCE(timestamp, ts, CURRENT_TIMESTAMP) AS timestamp,
  tags,
  CAST(metrics AS JSON)        AS metrics,
  config_hash
FROM alphas;
""")
con.close()

# 2) Construct registry AND pin every known path attribute to the same file
sig = inspect.signature(AlphaRegistry.__init__)
kw  = {}
for name in ("db_path","path","database"):
    if name in sig.parameters:
        kw[name] = str(db)
        break
reg = AlphaRegistry(**kw) if kw else AlphaRegistry(str(db))
for name in ("db_path","path","database"):
    if hasattr(reg, name):
        try: setattr(reg, name, str(db))
        except Exception: pass

# 3) Seed rows via registry
reg.register("h1", {"sharpe": 1.8}, ["demo"])
reg.register("h2", {"sharpe": 2.2}, ["demo"])

# 4) Refresh the 'runs' view again (post-insert; guarantees visibility)
c2 = duckdb.connect(str(db))
c2.execute("""
CREATE OR REPLACE VIEW runs AS
SELECT
  CAST(config_hash AS VARCHAR) AS alpha_id,
  CAST(id AS VARCHAR)          AS run_id,
  COALESCE(timestamp, ts, CURRENT_TIMESTAMP) AS timestamp,
  tags,
  CAST(metrics AS JSON)        AS metrics,
  config_hash
FROM alphas;
""")

# 5) Quick diagnostics to prove data is visible to analytics
print("[DIAG] counts:", c2.execute("SELECT (SELECT COUNT(*) FROM alphas) a, (SELECT COUNT(*) FROM runs) r").fetchone())
print("[DIAG] sample runs:\n", c2.execute("SELECT alpha_id, tags, json_extract(metrics, '$.sharpe') AS v FROM runs ORDER BY alpha_id LIMIT 5").df())
c2.close()

# 6) Now analytics should work
print("[INFO] Best top-2")
print(reg.rank(metric="sharpe", top_n=2))
print("[INFO] Summary")
print(reg.get_summary(metric="sharpe"))
"@

$tmp = [IO.Path]::GetTempFileName().Replace(".tmp",".py")
[IO.File]::WriteAllText($tmp, ($py -replace "`r?`n","`n"), (New-Object System.Text.UTF8Encoding($false)))

Write-Host "[INFO] Run smoke" -ForegroundColor Cyan
& $Python $tmp
if ($LASTEXITCODE -ne 0) { throw "Smoke failed" }

Remove-Item $tmp -Force -ErrorAction SilentlyContinue
Ok "Smoke okay"
