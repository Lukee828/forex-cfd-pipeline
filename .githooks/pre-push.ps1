# --- Hook env (PYTHONPATH, GIT_RD default) ---
try {
  $repo = (git rev-parse --show-toplevel).Trim()
} catch { $repo = (Get-Location).Path }
if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
  $env:PYTHONPATH = "$repo;$repo/src"
} elseif ($env:PYTHONPATH -notmatch [regex]::Escape("$repo/src")) {
  $env:PYTHONPATH = "$env:PYTHONPATH;$repo;$repo/src"
}
# default: skip remote dispatch unless explicitly opted in
if (-not $env:GIT_RD) { $env:GIT_RD = '0' }
# --- Auto-install base deps if requested ---
if ($env:GIT_AUTO_VENV -eq "1") {
  $pip = Join-Path (Join-Path $PWD ".venv") "Scripts\\pip.exe"
  if (Test-Path $pip) {
    Write-Host "[hook] Auto-installing base packages (numpy, pandas, pip-tools)..." -ForegroundColor DarkGray
    & $pip install numpy pandas pip-tools -q
  } else {
    Write-Warning "[hook] .venv not found for auto-install."
  }
}
#requires -Version 7
$ErrorActionPreference = 'Continue'
$PSStyle.OutputRendering = 'Host'

Write-Host "[pre-push] running checks..." -ForegroundColor Cyan

function Invoke-ZeroTouch {
  $p = Join-Path $PSScriptRoot '..\tools\Zero-Touch.ps1' | Resolve-Path -ErrorAction SilentlyContinue
  if ($p) {
    try { & pwsh -NoLogo -NoProfile -File $p }
    catch { Write-Host "[pre-push] Zero-Touch warning: $($_.Exception.Message)" -ForegroundColor Yellow }
  } else {
    Write-Host "[pre-push] Zero-Touch not present (skipping)" -ForegroundColor DarkGray
  }
}

function Ensure-Venv {
  if (Test-Path '.venv') { return }
  if ($env:GIT_AUTO_VENV -ne '1') { return }  # opt-in
  $py = Get-Command python -ErrorAction SilentlyContinue
  if (-not $py) { Write-Host "[pre-push] python not found; can't auto-create .venv" -ForegroundColor Yellow; return }
  try {
    Write-Host "[pre-push] creating .venv (opt-in)" -ForegroundColor DarkGray
    & $py.Source -m venv .venv | Out-Null
  } catch {
    Write-Host "[pre-push] failed to create .venv: $($_.Exception.Message)" -ForegroundColor Yellow
  }
}

function Invoke-RepoDoctor {
  $p = Join-Path $PSScriptRoot '..\tools\Repo-Doctor.ps1' | Resolve-Path -ErrorAction SilentlyContinue
  if ($p) {
    try {
      & pwsh -NoLogo -NoProfile -File $p -StopOnFail:$false   # no -Quiet
    } catch {
      Write-Host "[pre-push] Repo-Doctor warning: $($_.Exception.Message)" -ForegroundColor Yellow
    }
  } else {
    Write-Host "[pre-push] Repo-Doctor not present (skipping)" -ForegroundColor DarkGray
  }
}

if ($env:GIT_ZT -eq '0') { Write-Host "[pre-push] Zero-Touch disabled via GIT_ZT=0" -ForegroundColor DarkGray }
if ($env:GIT_RD -eq '0') { Write-Host "[pre-push] Repo-Doctor disabled via GIT_RD=0" -ForegroundColor DarkGray }

Ensure-Venv
if ($env:GIT_ZT -ne '0') { Invoke-ZeroTouch }
if ($env:GIT_RD -ne '0') { Invoke-RepoDoctor }

Write-Host "[pre-push] checks completed." -ForegroundColor Green
exit 0

# --- Autofix: stage & commit any changes made by pre-commit ---
try {
$dirty = git status --porcelain
  if (-not [string]::IsNullOrWhiteSpace($dirty)) {
    git add -A | Out-Null
    git commit -m "chore(pre-commit): apply EOF/trailing whitespace fixes" | Out-Null
    Write-Host "[hook] Committed pre-commit autofixes." -ForegroundColor DarkGray
  }
} catch {
  Write-Warning "[hook] Could not auto-commit pre-commit fixes: \"
}

# --- Autofix: stage & commit pre-commit changes (BEGIN) ---
try {
  \ = git status --porcelain
  if (-not [string]::IsNullOrWhiteSpace(\)) {
    git add -A | Out-Null
    git commit -m "chore(pre-commit): apply EOF/trailing whitespace fixes" | Out-Null
    Write-Host "[hook] Committed pre-commit autofixes." -ForegroundColor DarkGray
  } else {
    Write-Host "[hook] No pre-commit changes." -ForegroundColor DarkGray
  }
} catch {
  Write-Warning "[hook] Could not auto-commit pre-commit fixes: \"
}
# --- Autofix: stage & commit pre-commit changes (END) ---
