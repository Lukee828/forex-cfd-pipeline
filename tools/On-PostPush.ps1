param(
  [ValidateSet("draft","open","merged","abandoned")][string]$Status = "open",
  [ValidateSet("pass","fail","na")][string]$Pytest = "na",
  [ValidateSet("pass","fail","unknown")][string]$AiGuard = "unknown",
  [string]$Summary = ""
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$root = (git rev-parse --show-toplevel)
$man  = Join-Path $root "ai_lab/session_manifest.csv"
if (-not (Test-Path $man)) { throw "session_manifest.csv not found." }

$lines = Get-Content $man
if ($lines.Count -lt 2) { throw "No session rows to update." }
$header = $lines[0]
$rows = $lines[1..($lines.Count-1)]

# Update last row in-place (CSV is simple, we don’t reparse quoted commas)
$last = [string]$rows[-1]
$cols = $last -split ',(?=(?:[^""]*""[^""]*"")*[^""]*$)'
if ($cols.Count -lt 9) { throw "Last manifest row malformed (cols=$($cols.Count))." }

$cols[4] = $AiGuard
$cols[5] = $Pytest
$cols[6] = $Status
if ($Summary) { $cols[7] = '"' + $Summary + '"' }

$rows[$rows.Count-1] = ($cols -join ',')
@($header) + $rows | Set-Content -Encoding UTF8 $man
Write-Host "✔ Manifest updated: status=$Status, pytest=$Pytest, ai_guard=$AiGuard" -ForegroundColor Green
