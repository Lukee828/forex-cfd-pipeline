param(
  [Parameter(Mandatory=$true)][string]$Id,
  [string]$Title,
  [string]$Description,
  [string]$Owner,
  [string[]]$Labels,
  [string]$Status,
  [string]$Priority
)
# --- YAML module import (PSGallery module name: powershell-yaml) ---
$mod = Get-Module -ListAvailable powershell-yaml | Select-Object -First 1
if (-not $mod) {
  throw "Module 'powershell-yaml' not found. Install it with:
    Install-Module powershell-yaml -Scope CurrentUser -Force"
}
Import-Module $mod -ErrorAction Stop
# ---------------------------------------------------------------
$PlanPath = "ai_lab/plan.yaml"
$plan = ConvertFrom-Yaml (Get-Content -Raw $PlanPath)
$item = $plan.items | Where-Object { $_.id -eq $Id }
if (-not $item) { throw "No item with id $Id" }

if ($PSBoundParameters.ContainsKey("Title"))       { $item.title = $Title }
if ($PSBoundParameters.ContainsKey("Description")) { $item.description = $Description }
if ($PSBoundParameters.ContainsKey("Owner"))       { $item.owner = $Owner }
if ($PSBoundParameters.ContainsKey("Labels"))      { $item.labels = $Labels }
if ($PSBoundParameters.ContainsKey("Status"))      { $item.status = $Status }
if ($PSBoundParameters.ContainsKey("Priority"))    { $item.priority = $Priority }

$plan.updated = (Get-Date).ToString("yyyy-MM-dd")
$yaml = ConvertTo-Yaml -Data $plan
$yaml | Set-Content -Encoding UTF8 -NoNewline $PlanPath
Write-Host "Updated $Id" -ForegroundColor Cyan


