param([string]$Title = "feat: AlphaFactory + FeatureStore core", [string]$Body = "Draft PR body", [switch]$SkipDevSanity)
$ErrorActionPreference = "Stop"
$root = (git rev-parse --show-toplevel); if (-not $root) { throw "Not in a Git repo." }
Set-Location $root
$branch   = (git rev-parse --abbrev-ref HEAD).Trim()
$remote   = (git remote get-url origin).Trim()
if ($remote -match "[:/](?<owner>[^/]+)/(?<repo>[^/.]+)(?:\.git)?$") { $owner=$Matches.owner; $repo=$Matches.repo } else { throw "Cannot parse remote URL: $remote" }
if (-not $SkipDevSanity) {
  if (Test-Path ".venv/Scripts/pre-commit.exe") { .\.venv\Scripts\pre-commit.exe run -a }
  if (Test-Path ".venv/Scripts/python.exe")   { .\.venv\Scripts\python.exe -m pytest -q }
}
$t = [uri]::EscapeDataString($Title)
$b = [uri]::EscapeDataString($Body)
$url = "https://github.com/$owner/$repo/compare/$branch?expand=1&title=$t&body=$b"
Write-Host "Opening PR URL:" -ForegroundColor Cyan
Write-Host $url -ForegroundColor Yellow
Start-Process $url
