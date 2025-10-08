Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function _RepoRoot { (git rev-parse --show-toplevel) }
function _EnsureInRepo { if (-not (git rev-parse --is-inside-work-tree 2>$null)) { throw "Not inside a Git repository." } }
function _Exe([string]$exe) {
  $p = Join-Path (Join-Path (_RepoRoot) ".venv") ("Scripts\" + $exe)
  if (Test-Path $p) { return $p }
  return $exe
}

function Invoke-Precommit {
  _EnsureInRepo
  & (_Exe "pre-commit.exe") run -a
  if ($LASTEXITCODE) { throw "pre-commit failed ($LASTEXITCODE)" }
}

function Invoke-Tests {
  _EnsureInRepo
  & (_Exe "python.exe") -m pytest -q
  if ($LASTEXITCODE) { throw "pytest failed ($LASTEXITCODE)" }
}

function Sync-Registry {
  _EnsureInRepo
  $script = Join-Path (_RepoRoot) "tools/Sync-Registry.ps1"
  if (-not (Test-Path $script)) { throw "Missing: $script" }
  & pwsh -NoProfile -ExecutionPolicy Bypass -File $script
  if ($LASTEXITCODE) { throw "Sync-Registry.ps1 failed ($LASTEXITCODE)" }
}

function Finish-ReleaseTag {
  param([Parameter(Mandatory=$true)][string]$Tag)
  _EnsureInRepo
  $script = Join-Path (_RepoRoot) "tools/Finish-Release.ps1"
  if (-not (Test-Path $script)) { throw "Missing: $script" }
  & pwsh -NoProfile -ExecutionPolicy Bypass -File $script -Tag $Tag
  if ($LASTEXITCODE) { throw "Finish-Release.ps1 failed ($LASTEXITCODE)" }
}

function New-PullRequest {
  param(
    [string]$Title = "feat: AlphaFactory + FeatureStore core",
    [string]$Body  = "CI + tests green. Adds FeatureStore, ingest tool, registry sync.",
    [string]$Base  = ""
  )
  _EnsureInRepo
  $root = _RepoRoot; Set-Location $root
  $branch = (git rev-parse --abbrev-ref HEAD).Trim()
  $remote = (git remote get-url origin).Trim()
  if ($remote -notmatch "[:/](?<owner>[^/]+)/(?<repo>[^/.]+)(?:\.git)?$") { throw "Cannot parse remote: $remote" }
  $owner=$Matches.owner; $repo=$Matches.repo
  if (-not $Base) { $Base = (gh repo view "$owner/$repo" --json defaultBranchRef -q ".defaultBranchRef.name") }
  $t=[uri]::EscapeDataString($Title); $b=[uri]::EscapeDataString($Body); $eb=[uri]::EscapeDataString($branch)
  $url = "https://github.com/$owner/$repo/compare/$Base...$eb?expand=1&title=$t&body=$b"
  Write-Host "Opening PR URL:" -ForegroundColor Cyan
  Write-Host $url -ForegroundColor Yellow
  Start-Process $url
}

function Protect-DefaultBranch {
  param(
    [string[]]$Checks = @("lint","test"),
    [int]$RequiredApprovals = 1
  )
  _EnsureInRepo
  if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw "GitHub CLI (gh) not found." }
  $remote = (git remote get-url origin).Trim()
  if ($remote -notmatch "[:/](?<owner>[^/]+)/(?<repo>[^/.]+)(?:\.git)?$") { throw "Cannot parse remote: $remote" }
  $owner=$Matches.owner; $repo=$Matches.repo
  $default = gh repo view "$owner/$repo" --json defaultBranchRef -q ".defaultBranchRef.name"

  $payload = @{
    required_status_checks = @{ strict=$true; contexts=$Checks }
    enforce_admins = $true
    required_pull_request_reviews = @{ dismiss_stale_reviews=$true; required_approving_review_count=$RequiredApprovals }
    restrictions = $null
    required_linear_history = $true
    allow_force_pushes = $false
    allow_deletions   = $false
    block_creations   = $false
  }
  $tmp = New-TemporaryFile
  ($payload | ConvertTo-Json -Depth 8) | Set-Content -LiteralPath $tmp -Encoding utf8
  gh api --method PUT "repos/$owner/$repo/branches/$default/protection" -H "Accept: application/vnd.github+json" --input $tmp | Out-Null
  Remove-Item $tmp -Force

  # Try to enable "require conversation resolution" (ignore 404s)
  try {
    gh api --method PUT "repos/$owner/$repo/branches/$default/protection/required_conversation_resolution" -H "Accept: application/vnd.github+json" | Out-Null
  } catch { Write-Host "Note: conversation resolution endpoint not available (OK)." -ForegroundColor DarkYellow }

  # Verify core fields
  $jq = '{branch:"{0}",contexts:.required_status_checks.contexts,enforce_admins:.enforce_admins,linear:.required_linear_history,reviews:.required_pull_request_reviews.required_approving_review_count}' -f $default
  gh api "repos/$owner/$repo/branches/$default/protection" -q $jq
}


Export-ModuleMember -Function @(
  'Invoke-Precommit',
  'Invoke-Tests',
  'Sync-Registry',
  'Finish-ReleaseTag',
  'New-PullRequest',
  'Protect-DefaultBranch'
)
