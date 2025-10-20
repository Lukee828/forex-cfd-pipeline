param()
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "=== Fix-LF-Drift.ps1 ===" -ForegroundColor Cyan

# Ensure we are in a git repo
$root = (& git rev-parse --show-toplevel) 2>$null
if (-not $root) { throw "Not a git repo (git rev-parse failed)." }
Set-Location $root
Write-Host "Repo: $root" -ForegroundColor Gray

# 1) Ensure .gitattributes exists (LF everywhere for text)
$attrPath = Join-Path $root ".gitattributes"
if (-not (Test-Path $attrPath)) {
@"
* text=auto eol=lf
*.ps1   text eol=lf
*.py    text eol=lf
*.yml   text eol=lf
*.yaml  text eol=lf
*.md    text eol=lf
*.json  text eol=lf
*.csv   text eol=lf
*.txt   text eol=lf

*.png binary
*.jpg binary
*.jpeg binary
*.zip binary
*.pdf binary
"@ | Set-Content -Encoding UTF8 $attrPath
    Write-Host "Created .gitattributes (LF policy)" -ForegroundColor Green
}

# 2) Ensure .gitignore has some sensible defaults (create if missing; don’t overwrite)
$ignorePath = Join-Path $root ".gitignore"
if (-not (Test-Path $ignorePath)) {
@"
.pre-commit-cache/
.pre-commit-config.yaml.bak
.venv*/
__pycache__/
.DS_Store
Thumbs.db
"@ | Set-Content -Encoding UTF8 $ignorePath
    Write-Host "Created .gitignore" -ForegroundColor Green
}

# 3) Keep cache/bak stuff out of Git’s index
git restore --staged -A 2>$null | Out-Null
if (Test-Path ".pre-commit-cache") { git rm -r --cached .pre-commit-cache 2>$null | Out-Null }
if (Test-Path ".pre-commit-config.yaml.bak") { git rm --cached .pre-commit-config.yaml.bak 2>$null | Out-Null }

# 4) Normalize line endings safely (non-destructive)
git config core.autocrlf false
git add --renormalize . | Out-Null

# Commit normalization if there’s anything staged
$normNeeded = (git diff --cached --quiet) -ne $true
if ($normNeeded) {
    git commit -m "chore: normalize LF endings (auto-fix drift)" --no-verify | Out-Null
    Write-Host "Committed LF normalization." -ForegroundColor Green
} else {
    Write-Host "No normalization changes needed." -ForegroundColor DarkGray
}

# 5) Pre-commit: install only pre-commit hook; ensure config is valid
$env:PRE_COMMIT_COLOR = "never"
pre-commit uninstall --hook-type pre-push 2>$null | Out-Null
pre-commit install   --hook-type pre-commit | Out-Null
pre-commit validate-config

# 6) Run full hook suite on all files
Write-Host "Running pre-commit on all files..." -ForegroundColor Gray
pre-commit run --all-files -v

# 7) If hooks changed files, commit them
$hookChanges = (git status --porcelain) -ne $null -and -not [string]::IsNullOrWhiteSpace((git status --porcelain))
if ($hookChanges) {
    git add -A
    git commit -m "chore(pre-commit): apply hook autofixes" --no-verify | Out-Null
    Write-Host "Committed pre-commit autofixes." -ForegroundColor Green
} else {
    Write-Host "No pre-commit changes to commit." -ForegroundColor DarkGray
}

# 8) Push to current branch
$currentBranch = (git rev-parse --abbrev-ref HEAD).Trim()
Write-Host "Pushing branch: $currentBranch" -ForegroundColor Gray
git push

Write-Host "✅ Done: LF normalized, hooks applied, branch pushed." -ForegroundColor Green
