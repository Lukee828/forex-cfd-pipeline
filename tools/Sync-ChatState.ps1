param(
  [string]$Phase,
  [string]$Branch,
  [string]$ActiveFeature
)
$StatePath = "ai_lab/state.json"
$state = if (Test-Path $StatePath) { Get-Content -Raw $StatePath | ConvertFrom-Json } else { @{} }
if ($Phase)         { $state.phase = $Phase }
if ($Branch)        { $state.branch = $Branch }
if ($ActiveFeature) { $state.active_feature = $ActiveFeature }
$state.updated = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
$state | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 $StatePath
Write-Host "State synced → $StatePath" -ForegroundColor Green
