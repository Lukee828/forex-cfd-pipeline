# tools/AI-Guard.ps1
[CmdletBinding()]
param(
  [switch]$SkipLint,
  [switch]$SkipFormat,
  [switch]$SkipTests,
  [string[]]$PsPaths     = @('tools'),
  [string[]]$PythonPaths = @('src','tests','tools'),
  [string]  $Workflows   = '.github/workflows'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
try { $PSStyle.OutputRendering = 'Ansi' } catch {}

function Head($t){ Write-Host "`n=== $t ===" -ForegroundColor Cyan }
function Fail($m){ Write-Error $m; exit 1 }

# Resolve this script's path to avoid self-flagging
$SelfPath = (Resolve-Path -LiteralPath $MyInvocation.MyCommand.Path).Path

# ---------------------------------------------------------------------------
# 1) PS7 policy: every script has param(); forbid Read-Host in code
# ---------------------------------------------------------------------------
Head "PS7 policy checks"

# Gather PS files from the configured roots
$psFiles = @()
foreach ($p in $PsPaths) {
  if (Test-Path $p) {
    $psFiles += Get-ChildItem $p -Recurse -File -Include *.ps1,*.psm1
  }
}
# Exclude this very guard file
$psFiles = $psFiles | Where-Object { $_.FullName -ne $SelfPath }

$psBad = @()
foreach ($f in $psFiles) {
  $raw = Get-Content -Raw $f.FullName

  # Ignore pure-comment lines for Read-Host check
  $lines      = $raw -split "`r?`n"
  $nonComment = $lines | Where-Object { $_ -notmatch '^\s*#' }
  $code       = ($nonComment -join "`n")

  if ($raw -notmatch '^\s*param\s*\(') {
    $psBad += "[$($f.FullName)] missing param() block"
  }
  if ($code -match '(?i)\bRead-Host\b') {
    $psBad += "[$($f.FullName)] uses Read-Host (forbidden)"
  }
}

if ($psBad) {
  $psBad | ForEach-Object { Write-Host $_ -ForegroundColor Red }
  Fail "PS7 policy violations."
} else {
  Write-Host "PS7 scripts OK." -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# 2) Python banned-call scan (restricted to src/, with exec/ allowlist)
#    - We enforce for library/runtime code.
#    - We SKIP any file under src/exec/ (CLI orchestrators).
#    - We also SKIP any file that contains the token:  # ai-guard: allow-subprocess
# ---------------------------------------------------------------------------
Head "Python banned-call scan"

$patterns = @(
  '\bsubprocess\.(Popen|run|call|check_(call|output))\b',
  '\bos\.system\(',
  '\basyncio\.create_subprocess'
)

$allowToken = '# ai-guard: allow-subprocess'

# Collect *.py only under src/
$pyFiles = @()
if (Test-Path 'src') {
  $pyFiles += Get-ChildItem 'src' -Recurse -File -Include *.py
}

$hits = @()
foreach ($f in $pyFiles) {
  # Skip any file under src/exec/ by default
  $rel = $f.FullName.Replace('\','/')
  if ($rel -match '/src/exec/') { continue }

  $raw = Get-Content -Raw $f.FullName

  # If the token is present, skip scanning this file too
  if ($raw -match [regex]::Escape($allowToken)) { continue }

  foreach ($rx in $patterns) {
    if ($raw -match $rx) {
      $hits += "[$($f.FullName)] matched: $rx"
    }
  }
}

if ($hits) {
  $hits | ForEach-Object { Write-Host $_ -ForegroundColor Red }
  Fail "Python banned-call violations."
} else {
  Write-Host "Python sources OK (no banned calls detected)." -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# 3) Workflow forbidden triggers: no push:, no pull_request_target:
# ---------------------------------------------------------------------------
Head "Workflow trigger guard"

$banned = @('^\s*push\s*:', '^\s*pull_request_target\s*:')

# Guard self-files so they don't self-flag
$guardSelf = @(
  (Join-Path $Workflows 'no-push-guard.yml'),
  (Join-Path $Workflows 'no-push-guard.yaml')
) | ForEach-Object { $_.Replace('\','/') }

$wf = if (Test-Path $Workflows) { Get-ChildItem $Workflows -File -Include *.yml,*.yaml } else { @() }
$badWf = @()
foreach ($f in $wf) {
  $path = $f.FullName.Replace('\','/')
  if ($guardSelf -contains $path) { continue }
  $raw = Get-Content -Raw $f.FullName
  if (($banned | ForEach-Object { $raw -match $_ }) -contains $true) {
    $badWf += $path
  }
}

if ($badWf) {
  $badWf | ForEach-Object { Write-Host "Forbidden trigger in: $_" -ForegroundColor Red }
  Fail "Forbidden workflow triggers."
} else {
  Write-Host "No forbidden triggers found." -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# 4) Ruff / Black / Pytest
# ---------------------------------------------------------------------------
Head "Ruff / Black / Pytest"
if (-not $SkipLint)   { python -m ruff check . }
if (-not $SkipFormat) { python -m black --check . }
if (-not $SkipTests)  { python -m pytest -q }

Write-Host "`nAI-GUARD: All active checks passed." -ForegroundColor Green
