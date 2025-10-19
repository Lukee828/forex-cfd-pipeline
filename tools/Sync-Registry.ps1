param()
[CmdletBinding()]
param()

# PS7-only
$ErrorActionPreference = "Stop"
$root = (Get-Location).Path
$py   = Join-Path $root ".venv\Scripts\python.exe"
$sync = Join-Path $root "tools\sync_registry.py"

if (-not (Test-Path $py))   { throw "Python not found: $py" }
if (-not (Test-Path $sync)) { throw "sync_registry.py not found: $sync" }

$dataDir = Join-Path $root ".data"
if (-not (Test-Path $dataDir)) { New-Item -ItemType Directory -Path $dataDir | Out-Null }
$db = Join-Path $dataDir "alpha_registry.db"

# Use the path AS-IS in a double-quoted Python raw string (no need to escape single quotes)
$pycode = @"
import sqlite3, json, pathlib, os
db = pathlib.Path(r"$db")
# ensure parent exists (defense-in-depth)
db.parent.mkdir(parents=True, exist_ok=True)
con = sqlite3.connect(db)
cur = con.cursor()
try:
    cur.execute("CREATE TABLE IF NOT EXISTS factors (name TEXT PRIMARY KEY)")
    cols = [r[1] for r in cur.execute("PRAGMA table_info(factors)")]
    def ensure(coldef, name):
        if name not in cols:
            cur.execute(f"ALTER TABLE factors ADD COLUMN {coldef}")
    ensure("impl TEXT", "impl")
    ensure("params TEXT", "params")
    ensure("params_json TEXT", "params_json")
    ensure("created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "created_at")
    ensure("updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "updated_at")
    con.commit()
finally:
    con.close()
print("Schema migration OK ->", db)
"@

$pycode | & $py -
if ($LASTEXITCODE) { throw "Migration failed ($LASTEXITCODE)" }

& $py $sync --db $db --verbose
if ($LASTEXITCODE) { throw "sync_registry.py failed ($LASTEXITCODE)" }

Write-Host "✓ Registry DB migrated and synced successfully." -ForegroundColor Green
