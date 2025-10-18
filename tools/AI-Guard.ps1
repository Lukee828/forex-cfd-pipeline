param(
  [string]$PyExe = $null,
  [string]$PolicyPath = "policy.yaml",
  [switch]$ReportOnly
)
$ErrorActionPreference = "Stop"

# Skip on non-Windows
if (-not $IsWindows) {
  Write-Host "AI-Guard: skipping on non-Windows runner."
  exit 0
}

# Autodetect Python
if (-not $PyExe) {
  if ($IsWindows -and (Test-Path ".\.venv311\Scripts\python.exe")) {
    $PyExe = ".\.venv311\Scripts\python.exe"
  } elseif ($cmd = Get-Command python -ErrorAction SilentlyContinue) {
    $PyExe = $cmd.Source
  } else {
    $PyExe = "python"
  }
}: $($f.FullName)" }
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


