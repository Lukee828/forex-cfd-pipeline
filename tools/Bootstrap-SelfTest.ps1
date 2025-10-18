# --- CI guard: skip on non-Windows runners ---
if (-not $IsWindows) {
  Write-Host "Bootstrap-SelfTest: skipping on non-Windows runner."
  exit 0
}
# Ensure PowerShell.Yaml is available for ConvertFrom-Yaml
try {
  if (-not (Get-Module -ListAvailable -Name PowerShell.Yaml)) {
    Install-Module PowerShell.Yaml -Scope CurrentUser -Force -Confirm:$false
  }
  Import-Module PowerShell.Yaml -ErrorAction Stop
} catch {
  Write-Warning "PowerShell.Yaml not available; YAML-based checks will be skipped."
}
param()
$ErrorActionPreference='Stop'
Write-Host '== Bootstrap Self-Test ==' -ForegroundColor Cyan
$policy = Get-Content policy.yaml -Raw | ConvertFrom-Yaml 2>$null
if(-not $policy.network.no_network){ Write-Host 'no_network must be true' -ForegroundColor Red; exit 1 }
Write-Host 'Policy local-only: OK' -ForegroundColor Green
pwsh tools/AI-Guard.ps1
if($LASTEXITCODE -ne 0){ exit $LASTEXITCODE }
.\.venv311\Scripts\python.exe -m pytest tests/policy -q
if($LASTEXITCODE -ne 0){ exit $LASTEXITCODE }
Start-Process -FilePath .\.venv311\Scripts\python.exe -ArgumentList ' -m uvicorn ai_lab.serve_agent:app --host 127.0.0.1 --port 8000' -PassThru | ForEach-Object {
  Start-Sleep -Seconds 2
  try {
    $res = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -UseBasicParsing -TimeoutSec 5
    if($res.StatusCode -ne 200){ throw 'Agent health failed.' }
    Write-Host 'Agent /health: OK' -ForegroundColor Green
  } catch { Write-Host $_ -ForegroundColor Red; exit 1 }
  finally { Get-Process -Name 'python' | Where-Object { $_.Path -like '*\.venv311\Scripts\python.exe' } | Stop-Process -Force -ErrorAction SilentlyContinue }
}
Write-Host '== All checks passed ==' -ForegroundColor Green


