param(
  [Parameter(Mandatory=$true)][string]$Title,
  [string]$Description = "",
  [string]$Owner = "unassigned",
  [string[]]$Labels = @(),
  [ValidateSet("planned","in_progress","done","blocked")][string]$Status = "planned",
  [string]$Priority = "P3:normal"
)

$ErrorActionPreference = 'Stop'
# --- YAML module import (PSGallery module name: powershell-yaml) ---
$mod = Get-Module -ListAvailable powershell-yaml | Select-Object -First 1
if (-not $mod) {
  throw "Module 'powershell-yaml' not found. Install it with:
    Install-Module powershell-yaml -Scope CurrentUser -Force"
}
Import-Module $mod -ErrorAction Stop
# ---------------------------------------------------------------

$PlanPath = "ai_lab/plan.yaml"
if (-not (Test-Path $PlanPath)) { throw "Plan file not found: $PlanPath" }

$plan = ConvertFrom-Yaml (Get-Content -Raw $PlanPath)
if (-not $plan.items) { $plan.items = @() }

$Id = "PL-" + (Get-Date).ToString("yyyyMMdd-HHmmss")

$item = [ordered]@{
  id          = $Id
  title       = $Title
  description = $Description
  owner       = $Owner
  labels      = $Labels
  status      = $Status
  priority    = $Priority
  created     = (Get-Date).ToString("yyyy-MM-dd")
}

$plan.items  = @($plan.items + @($item))
$plan.updated = (Get-Date).ToString("yyyy-MM-dd")

$yaml = ConvertTo-Yaml -Data $plan
$yaml | Set-Content -Encoding UTF8 -NoNewline $PlanPath

Write-Host ("Added {0}: {1}" -f $Id, $Title) -ForegroundColor Green


