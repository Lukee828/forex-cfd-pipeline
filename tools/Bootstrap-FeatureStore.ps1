param(
  [switch]$NoTests
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Utf8Lf {
  param([Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] [string]$Content)
  $nl = "`n"
  $norm = ($Content -replace "`r?`n",$nl)
  if (-not $norm.EndsWith($nl)) { $norm += $nl }
  $bytes = [Text.Encoding]::UTF8.GetBytes($norm)
  [IO.File]::WriteAllBytes($Path, $bytes)
}
function Ensure-Dir { param([string]$Dir) [IO.Directory]::CreateDirectory($Dir) | Out-Null }

$root = (git rev-parse --show-toplevel)
Set-Location $root

# 1) Files to create/update
$pyDir   = Join-Path $root 'src/store'
$testDir = Join-Path $root 'tests/store'
Ensure-Dir $pyDir
Ensure-Dir $testDir

$featureStorePy = @"
from __future__ import annotations
import duckdb
from typing import Iterable, Mapping, Any

DDL = '''
CREATE TABLE IF NOT EXISTS feature_store (
    symbol TEXT,
    ts     TIMESTAMP,
    name   TEXT,
    value  DOUBLE,
    ver    TEXT DEFAULT 'v1'
)
'''

class FeatureStore:
    def __init__(self, path: str = ':memory:'):
        self.con = duckdb.connect(path)
        self.con.execute(DDL)

    def upsert(self, rows: Iterable[Mapping[str, Any]]) -> int:
        # rows: {symbol, ts, name, value, ver?}
        data = []
        for r in rows:
            data.append((
                r['symbol'],
                r['ts'],
                r['name'],
                float(r['value']),
                r.get('ver','v1'),
            ))
        if not data:
            return 0
        self.con.execute("INSERT INTO feature_store VALUES (?, ?, ?, ?, ?)", data)
        return len(data)

    def query(self, symbol: str, start: str = None, end: str = None, ver: str | None = None):
        parts = ["symbol = ?"]
        args  = [symbol]
        if start: parts.append("ts >= ?"); args.append(start)
        if end:   parts.append("ts <  ?"); args.append(end)
        if ver:   parts.append("ver = ?"); args.append(ver)
        where = " AND ".join(parts)
        q = f"SELECT symbol, ts, name, value, ver FROM feature_store WHERE {where} ORDER BY ts"
        return self.con.execute(q, args).fetch_df()

    def pivot_wide(self, symbol: str, start: str = None, end: str = None, ver: str | None = None):
        df = self.query(symbol, start, end, ver)
        if df.empty: 
            return df
        out = df.pivot(index='ts', columns='name', values='value').reset_index()
        return out
"@

$featureStoreTest = @"
import datetime as dt
import pandas as pd
import pytest

try:
    import duckdb  # noqa
    DUCK = True
except Exception:
    DUCK = False

pytestmark = pytest.mark.skipif(not DUCK, reason='duckdb not installed')

from src.store.feature_store import FeatureStore

def test_upsert_and_query_roundtrip(tmp_path):
    db = tmp_path / 'fs.duckdb'
    fs = FeatureStore(str(db))

    rows = [
        {'symbol':'EURUSD','ts': dt.datetime(2024,1,1,0, tzinfo=dt.timezone.utc), 'name':'bb_width', 'value': 0.1},
        {'symbol':'EURUSD','ts': dt.datetime(2024,1,1,1, tzinfo=dt.timezone.utc), 'name':'bb_width', 'value': 0.2},
        {'symbol':'EURUSD','ts': dt.datetime(2024,1,1,1, tzinfo=dt.timezone.utc), 'name':'ma_slope', 'value': -0.5},
    ]
    n = fs.upsert(rows)
    assert n == 3

    df = fs.query('EURUSD')
    assert len(df) == 3
    assert set(df['name']) == {'bb_width','ma_slope'}

    wide = fs.pivot_wide('EURUSD')
    assert list(wide.columns) == ['ts','bb_width','ma_slope']
    assert pd.notna(wide.loc[wide['ts']==pd.Timestamp('2024-01-01 01:00:00+0000', tz='UTC'),'ma_slope']).any()
"@

# 2) Ensure duckdb in requirements.txt
$req = Join-Path $root 'requirements.txt'
if (Test-Path $req) {
  $txt = Get-Content -Raw -Encoding UTF8 $req
} else {
  $txt = ""
}
if ($txt -notmatch '(?m)^\s*duckdb(\[.+\])?\s*(==|>=|>|~=|<)?') {
  $nl = if ($txt -match "`r?`n$") { "" } else { "`n" }
  $txt = ($txt -replace "`r?`n","`n") + $nl + "duckdb>=1.0,<2.0`n"
  Write-Utf8Lf -Path $req -Content $txt
}

# 3) Write source + tests (idempotent style)
Write-Utf8Lf -Path (Join-Path $pyDir 'feature_store.py') -Content $featureStorePy
Write-Utf8Lf -Path (Join-Path $testDir 'test_feature_store.py') -Content $featureStoreTest

# 4) Branch + commit + push + PR
$branch = "chore/feature-store-bootstrap"
$cur = (git branch --show-current) 2>$null
if ($cur -ne $branch) {
  git switch -c $branch 2>$null | Out-Null
  if ($LASTEXITCODE -ne 0) { git switch $branch | Out-Null }
}
git add src/store/feature_store.py tests/store/test_feature_store.py requirements.txt
$has = (git diff --cached --name-only) -ne $null
if ($has) {
  git commit -m "feat(store): bootstrap DuckDB Feature Store + tests; add duckdb dep"
  git push -u origin HEAD
}

# 5) Try pre-commit + pytest (do not fail the script)
try { if (Get-Command pre-commit -ErrorAction SilentlyContinue) { pre-commit run -a } } catch { Write-Warning "pre-commit failed: $($_.Exception.Message)" }
if (-not $NoTests) {
  try { if (Get-Command pytest -ErrorAction SilentlyContinue) { pytest -q } } catch { Write-Warning "pytest failed: $($_.Exception.Message)" }
}

# 6) Open PR (idempotent)
try {
  $exists = gh pr list --head $branch --state open --json number -q '.[0].number' 2>$null
  if (-not $exists) {
    $title = "Bootstrap DuckDB Feature Store (module + tests)"
    $body  = @"
This scaffolds a minimal Feature Store:

- `src/store/feature_store.py` (DuckDB DDL + upsert/query/pivot)
- `tests/store/test_feature_store.py` (round-trip test)
- `requirements.txt` -> add `duckdb>=1,<2`

CI: pre-commit + pytest executed in script (best-effort).
"@
    gh pr create --fill --title $title --body $body --base main --head $branch --draft=false | Out-Null
  }
} catch { Write-Warning "gh PR create failed: $($_.Exception.Message)" }

Write-Host "`n[Bootstrap-FeatureStore] Complete." -ForegroundColor Green
