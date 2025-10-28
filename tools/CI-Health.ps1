param([switch]$Dispatch)

$ErrorActionPreference = 'Stop'
function Banner($t,$ok=$true){ $c = if($ok){'Green'} else {'Red'}; Write-Host "== $t ==" -ForegroundColor $c }

# 1) Git sanity
$branch = (git rev-parse --abbrev-ref HEAD).Trim()
$dirty  = (git status --porcelain)
Banner "Branch: $branch  |  Dirty: $([bool]$dirty -as [string])" -not $dirty

# 2) Pre-commit suite
pre-commit run --all-files --show-diff-on-failure | Out-Host

# 3) Workflow guard (no push / no pull_request_target)
$bad = $false
Get-ChildItem .github/workflows -File -Include *.yml,*.yaml | ForEach-Object {
  $t = Get-Content -Raw -Encoding UTF8 $_.FullName
  if ($t -match '^\s*push\s*:' -or $t -match '^\s*pull_request_target\s*:') {
    Write-Host "FORBIDDEN: $($_.Name)" -ForegroundColor Red; $bad = $true
  } else { Write-Host "OK: $($_.Name)" -ForegroundColor Green }
}
if ($bad) { throw "Forbidden triggers present." }

# 4) Optional: dispatch meta-alloc smoke and fetch artifact
$wf = '.github/workflows/meta-alloc-smoke.yml'
if ($Dispatch) {
  gh workflow run $wf | Out-Host
  $rid = $null
  for ($i=0; $i -lt 30 -and -not $rid; $i++){ Start-Sleep 1; $rid = gh run list --workflow $wf -L 1 --json databaseId --jq '.[0].databaseId' }
  if (-not $rid) { throw "No run appeared for $wf." }
  gh run view $rid --json status,conclusion,url | ConvertFrom-Json | Format-List
  $dest = "artifacts/ci-meta/$rid"; if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
  New-Item -ItemType Directory -Force -Path $dest | Out-Null
  gh run download $rid --name allocations --dir $dest 2>$null
  Write-Host "Artifacts in $dest" -ForegroundColor Cyan
  Get-ChildItem $dest -Recurse | Format-Table -Auto
}

Banner "CI health check complete"
