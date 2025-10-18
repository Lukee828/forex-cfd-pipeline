param(
  [string]$PyExe = ".\.venv311\Scripts\python.exe",
  [string]$PolicyPath = "policy.yaml",
  [switch]$ReportOnly
)
$ErrorActionPreference = "Stop"
function Fail($m){ Write-Host "AI-GUARD: $m" -ForegroundColor Red; exit 1 }
$violations = [System.Collections.Generic.List[string]]::new()
function Report($m){ $violations.Add($m); Write-Host $m -ForegroundColor Yellow }

function Read-Yaml($Path){
  if (Get-Command ConvertFrom-Yaml -ErrorAction SilentlyContinue) {
    return Get-Content $Path -Raw | ConvertFrom-Yaml
  }
  $py = @"
import sys, json, yaml
print(json.dumps(yaml.safe_load(open(sys.argv[1],'r',encoding='utf-8').read()), ensure_ascii=False))
"@
  $json = & $PyExe -c $py $Path
  return $json | ConvertFrom-Json
}

if (-not (Test-Path $PolicyPath)) { Fail "Missing $PolicyPath" }
$policy = Read-Yaml $PolicyPath

Write-Host "→ Ruff" -ForegroundColor Cyan
& $PyExe -m ruff check . | Out-Host
if ($LASTEXITCODE -ne 0) { if ($ReportOnly){ Report "Ruff failed." } else { Fail "Ruff failed." } }

Write-Host "→ Black --check" -ForegroundColor Cyan
& $PyExe -m black --check . | Out-Host
if ($LASTEXITCODE -ne 0) { if ($ReportOnly){ Report "Black check failed." } else { Fail "Black check failed." } }

# === file sets (skip .git, venv, Scripts, __pycache__, build) ===
$pyFiles = Get-ChildItem -Recurse -Include *.py -File | Where-Object {
  $_.FullName -notmatch '\\.git' -and $_.FullName -notmatch 'venv' -and
  $_.FullName -notmatch '\\build\\' -and $_.FullName -notmatch '__pycache__'
}
$psFiles = Get-ChildItem -Recurse -Include *.ps1 -File | Where-Object {
  $_.FullName -notmatch '\\.git' -and $_.FullName -notmatch 'venv' -and
  $_.FullName -notmatch '\\Scripts\\' -and $_.FullName -notmatch '\\build\\'
}

# === python content rules ===
foreach($f in $pyFiles){
  $t = Get-Content $f.FullName -Raw
  foreach($imp in $policy.python.forbidden_imports){
    if($t -match "^\s*import\s+$imp\b|^\s*from\s+$imp\b"){
      if ($ReportOnly){ Report "$($f.FullName): import $imp" } else { Fail "$($f.FullName): import $imp" }
    }
  }
  foreach($call in $policy.python.forbidden_calls){
    if($t -match [Regex]::Escape($call)){
      if ($ReportOnly){ Report "$($f.FullName): call $call" } else { Fail "$($f.FullName): call $call" }
    }
  }
  if($policy.network.no_network){
    foreach($imp in $policy.network.python_forbidden_imports){
      if($t -match "^\s*import\s+$imp\b|^\s*from\s+$imp\b"){
        if ($ReportOnly){ Report "$($f.FullName): NET import $imp" } else { Fail "$($f.FullName): NET import $imp" }
      }
    }
    foreach($call in $policy.network.python_forbidden_calls){
      if($t -match [Regex]::Escape($call)){
        if ($ReportOnly){ Report "$($f.FullName): NET call $call" } else { Fail "$($f.FullName): NET call $call" }
      }
    }
    if($t -match 'https?://(?!127\.0\.0\.1|localhost)'){
      if ($ReportOnly){ Report "$($f.FullName): outbound URL detected" } else { Fail "$($f.FullName): outbound URL detected" }
    }
  }
}

# === powershell content rules ===
foreach($f in $psFiles){
  $t = Get-Content $f.FullName -Raw
  if($policy.powershell.require_param_block -and ($t -notmatch '^\s*(?:\[[^\]]+\]\s*)*param\(')){
    if ($ReportOnly){ Report "PS1 missing param(): $($f.FullName)" } else { Fail "PS1 missing param(): $($f.FullName)" }
  }
  foreach($cmd in $policy.powershell.forbidden_cmdlets){
    if($t -match "\b$cmd\b"){
      if ($ReportOnly){ Report "Forbidden cmdlet $cmd in $($f.FullName)" } else { Fail "Forbidden cmdlet $cmd in $($f.FullName)" }
    }
  }
  if($t -match 'Start-Sleep\s+-Seconds\s+(\d+)'){
    $m = [int]$Matches[1]
    if($m -gt [int]$policy.powershell.max_sleep_seconds){
      if ($ReportOnly){ Report "Start-Sleep $m>s in $($f.FullName)" } else { Fail "Start-Sleep $m>s in $($f.FullName)" }
    }
  }
  if($policy.network.no_network){
    foreach($cmd in $policy.network.powershell_forbidden_cmdlets){
      if($t -match "\b$cmd\b"){
        if ($ReportOnly){ Report "Forbidden NET cmdlet $cmd in $($f.FullName)" } else { Fail "Forbidden NET cmdlet $cmd in $($f.FullName)" }
      }
    }
    if($t -match 'https?://(?!127\.0\.0\.1|localhost)'){
      if ($ReportOnly){ Report "Outbound URL detected in $($f.FullName)" } else { Fail "Outbound URL detected in $($f.FullName)" }
    }
  }
}

Write-Host "→ PyTest" -ForegroundColor Cyan
& $PyExe -m pytest -q | Out-Host
if ($LASTEXITCODE -ne 0) { if ($ReportOnly){ Report "PyTest failed." } else { Fail "PyTest failed." } }

if ($ReportOnly -and $violations.Count) { exit 1 }
Write-Host "AI-GUARD: PASS" -ForegroundColor Green
