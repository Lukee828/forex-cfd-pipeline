param(
  [switch]$Json,
  [string]$Status
)
$ErrorActionPreference = 'Stop'

# Require YAML module
Import-Module powershell-yaml -ErrorAction Stop

# Locate plan file relative to this script
$planPath = Join-Path $PSScriptRoot '..\ai_lab\plan.yaml' | Resolve-Path -ErrorAction Stop

# Load plan and items (ConvertFrom-Yaml returns hashtables)
$plan  = ConvertFrom-Yaml (Get-Content -Raw $planPath)
$items = @($plan.items)

if (-not $items -or -not $items.Count) {
  Write-Host "No items found in $planPath"
  Write-Host "Tip: .\tools\Plan-Add.ps1 -Title 'My Task' -Owner 'you' -Labels infra -Status planned -Priority 'P3:medium'" -ForegroundColor DarkGray
  exit 0
}

# Optional filter
if ($Status) { $items = $items | Where-Object { $_.status -eq $Status } }

# Output
if ($Json) {
  $items | ConvertTo-Json -Depth 10
} else {
  # Coerce hashtables -> PSCustomObject so Format-Table can see properties
  $items |
    ForEach-Object { [pscustomobject]$_ } |
    Sort-Object id |
    Format-Table id,title,status,owner,priority -AutoSize
}
