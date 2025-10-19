param(
  [switch]$SkipLint,
  [switch]$SkipFormat,
  [switch]$SkipTests,
  [string[]]$PsPaths     = @('tools'),
  [string[]]$PythonPaths = @('src','tests','tools'),
  [string]  $Workflows   = '.github/workflows'
)

function Head($t){ Write-Host "`n=== $t ===" -ForegroundColor Cyan }
function Fail($m){ Write-Error $m; exit 1 }

$ErrorActionPreference = 'Stop'

# Resolve this script path (PS7-safe)
$SelfPath = $PSCommandPath
if ([string]::IsNullOrEmpty($SelfPath)) { $SelfPath = $MyInvocation.MyCommand.Path }
if (-not [string]::IsNullOrEmpty($SelfPath)) { $SelfPath = (Resolve-Path -LiteralPath $SelfPath).Path }

# --- PS7 policy (param() + no Read-Host)
Head "PS7 policy checks"
$psFiles = @()
foreach($p in $PsPaths){
  if (Test-Path $p) { $psFiles += Get-ChildItem $p -Recurse -File -Include *.ps1,*.psm1 }
}
if ($SelfPath) { $psFiles = $psFiles | Where-Object { $_.FullName -ne $SelfPath } }

$psBad = @()
foreach($f in $psFiles){
  $raw = Get-Content -Raw $f.FullName
  $lines = $raw -split "`r?`n"
  $nonComment = $lines | Where-Object { $_ -notmatch '^\s*#' }
  $code = ($nonComment -join "`n")
  if ($raw -notmatch '^\s*param\s*\(') { $psBad += "[$($f.FullName)] missing param() block" }
  if ($code -match '(?i)\bRead-Host\b') { $psBad += "[$($f.FullName)] uses Read-Host (forbidden)" }
}
if($psBad){ $psBad | ForEach-Object { Write-Host $_ -ForegroundColor Red }; Fail "PS7 policy violations." }
else{ Write-Host "PS7 scripts OK." -ForegroundColor Green }

# --- Python banned-call scan
Head "Python banned-call scan"
$patterns = @(
  '\bsubprocess\.(Popen|run|call|check_(call|output))\b',
  '\bos\.system\(',
  '\basyncio\.create_subprocess'
)
$pyFiles = @()
foreach($p in $PythonPaths){
  if (Test-Path $p) { $pyFiles += Get-ChildItem $p -Recurse -File -Include *.py }
}
function Normalize-Path([string]$p) { return $p.Replace('\','/').ToLower() }

# Allowlist as ONE regex against normalized path (repo-tail match)
$allowRegex = '/(src/exec/(daily_run|refresh_prices|run_all|sweep_robustness|walkforward)\.py|tests/alpha_factory/test_registry_cli_v0(26|28)\.py|tools/repo_doctor\.py)$'

$hits = @()
foreach($f in $pyFiles){
  $raw  = Get-Content -Raw $f.FullName
  $norm = Normalize-Path $f.FullName
  foreach($rx in $patterns){
    if ($raw -match $rx) {
      if ($norm -notmatch $allowRegex) { $hits += "[$($f.FullName)] matched: $rx" }
    }
  }
}
if($hits){ $hits | ForEach-Object { Write-Host $_ -ForegroundColor Red }; Fail "Python banned-call violations." }
else{ Write-Host "Python sources OK (no banned calls outside allowlist)." -ForegroundColor Green }

# --- Workflow forbidden triggers (allow lint/test by basename)
Head "Workflow trigger guard"
$banned = @('(?m)^\s*push\s*:', '(?m)^\s*pull_request_target\s*:')

$guardSelf = @(
  (Join-Path $Workflows 'no-push-guard.yml'),
  (Join-Path $Workflows 'no-push-guard.yaml')
) | ForEach-Object { $_.Replace('\','/') }

$allowBase = @('lint','test')  # basenames allowed to have push:

$wf = if (Test-Path $Workflows) {
  Get-ChildItem -Path (Join-Path $Workflows '*') -File |
    Where-Object { $_.Extension -in '.yml', '.yaml' }
} else { @() }

$badWf = @()
foreach($f in $wf){
  $base = [IO.Path]::GetFileNameWithoutExtension($f.Name).ToLower()
  $path = $f.FullName.Replace('\','/')
  if ($guardSelf -contains $path) { continue }
  if ($allowBase -contains $base) { continue }
  $raw = Get-Content -Raw $f.FullName
  if (($banned | ForEach-Object { $raw -match $_ }) -contains $true) { $badWf += $path }
}

if($badWf){
  $badWf | ForEach-Object { Write-Host "Forbidden trigger in: $_" -ForegroundColor Red }
  Fail "Forbidden workflow triggers."
} else {
  Write-Host "No forbidden triggers found." -ForegroundColor Green
}

# --- Ruff / Black / Pytest
Head "Ruff / Black / Pytest"
if (-not $SkipLint)   { python -m ruff check . }
if (-not $SkipFormat) { python -m black --check . }
if (-not $SkipTests)  { python -m pytest -q }

Write-Host "`nAI-GUARD: All active checks passed." -ForegroundColor Green