# tools/Start-MT5-Bridge.ps1
[CmdletBinding()]
param([string]$Config = "configs/bridge_mt5.yaml")
$ErrorActionPreference = 'Stop'

function Resolve-RepoRoot {
  param([string]$ScriptDir)
  $candidates = @()
  if ($ScriptDir) { $candidates += $ScriptDir }
  $pscp = $PSCommandPath; if ($pscp) { $candidates += (Split-Path -Parent $pscp) }
  $micp = $MyInvocation.MyCommand.Path; if ($micp) { $candidates += (Split-Path -Parent $micp) }
  $candidates += (Get-Location).Path
  foreach ($base in $candidates | Get-Unique) {
    try { $dir = Get-Item -LiteralPath $base -ErrorAction Stop } catch { continue }
    for ($i=0; $i -lt 8; $i++) {
      $hasTools = Test-Path -LiteralPath (Join-Path $dir.FullName "tools") -PathType Container
      $hasPkg   = Test-Path -LiteralPath (Join-Path $dir.FullName "alpha_factory") -PathType Container
      if ($hasTools -and $hasPkg) { return $dir.FullName }
      $dir = $dir.Parent; if (-not $dir) { break }
    }
  }
  return $null
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot  = Resolve-RepoRoot -ScriptDir $scriptDir
if ([string]::IsNullOrWhiteSpace($repoRoot)) {
  throw "Unable to resolve repo root. Ensure it contains 'tools\' and 'alpha_factory\'."
}

$py = Join-Path $repoRoot ".venv311\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $py)) {
  throw "Python venv not found at $py. Create .venv311 with Python 3.11."
}

$pushed = $false
try {
  Push-Location -Path $repoRoot
  $pushed = $true
  & $py -m alpha_factory.bridge.bridge_mt5 --config $Config --serve
} finally {
  if ($pushed) { Pop-Location }
}