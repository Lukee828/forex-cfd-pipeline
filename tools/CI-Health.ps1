param(
  [switch]$Dispatch
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Banner([string]$t){ Write-Host "== $t ==" -ForegroundColor Cyan }

# 1) Git sanity
$branch = (git rev-parse --abbrev-ref HEAD).Trim()
$dirty  = -not [string]::IsNullOrWhiteSpace((git status --porcelain))
Banner "Branch: $branch  |  Dirty: $dirty"
if ($branch -ne 'main') { Write-Warning "Not on 'main' — continuing, but results may differ." }

# 2) Pre-commit suite (allow one auto-fix pass)
& pre-commit run --all-files --show-diff-on-failure | Out-Host
$ec = $LASTEXITCODE
if ($ec -ne 0) {
  Write-Host "Pre-commit requested fixes; re-running once..." -ForegroundColor Yellow
  & pre-commit run --all-files --show-diff-on-failure | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "pre-commit failed (after auto-fix retry)" }
}

# 3) Workflow guard (no push / no pull_request_target)
$bad = $false
Get-ChildItem .github/workflows -File -Include *.yml,*.yaml -ErrorAction SilentlyContinue | ForEach-Object {
  $t = Get-Content -Raw -Encoding UTF8 $_.FullName
  if ([regex]::IsMatch($t,'(?m)^\s*push\s*:') -or [regex]::IsMatch($t,'(?m)^\s*pull_request_target\s*:')) {
    Write-Host "FORBIDDEN: $($_.Name)" -ForegroundColor Red; $bad = $true
  } else {
    Write-Host "OK: $($_.Name)" -ForegroundColor Green
  }
}
if ($bad) { throw "Forbidden triggers present." }

# 4) Optional: dispatch Meta Allocator smoke and fetch artifact
if ($Dispatch) {
  $wf = '.github/workflows/meta-alloc-smoke.yml'
  Write-Host "Dispatching $wf ..." -ForegroundColor Cyan
  gh workflow run $wf | Out-Host

  # wait for GH to index the run
  $rid = $null
  for ($i=0; $i -lt 45 -and -not $rid; $i++) {
    Start-Sleep 1
    $rid = gh run list --workflow $wf -L 1 --json databaseId --jq '.[0].databaseId' 2>$null
  }
  if (-not $rid) { throw "No run appeared for $wf." }

  gh run view $rid --json status,conclusion,url,headSha | ConvertFrom-Json | Format-List | Out-Host

  $dest = Join-Path "artifacts/ci-meta" $rid
  if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
  New-Item -ItemType Directory -Force -Path $dest | Out-Null

  # try to download allocation csvs (resilient)
  try {
    gh run download $rid --name allocations --dir $dest 2>$null
  } catch { }

  Write-Host "`nArtifacts in $dest" -ForegroundColor Cyan
  if (Test-Path $dest) { Get-ChildItem $dest -Recurse | Format-Table -Auto | Out-Host }
}

Banner "CI health check complete"
