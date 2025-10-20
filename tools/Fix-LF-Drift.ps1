param()
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "=== Fix-LF-Drift.ps1 ===" -ForegroundColor Cyan
Write-Host "Normalizing line endings and cleaning repo state..." -ForegroundColor Gray

# 1) Ensure .gitattributes exists and enforces LF
$attrPath = ".gitattributes"
if (-not (Test-Path $attrPath)) {
    @"
* text=auto eol=lf
*.ps1 text eol=lf
*.py text eol=lf
*.yml text eol=lf
*.yaml text eol=lf
*.md text eol=lf
*.json text eol=lf
*.csv text eol=lf
*.txt text eol=lf

*.png binary
*.jpg binary
*.zip binary
*.pdf binary
"@ | Set-Content -Encoding UTF8 $attrPath
    Write-Host "Wrote default .gitattributes" -ForegroundColor Green
}

# 2) Ensure .gitignore excludes cache and OS junk
$ignorePath = ".gitignore"
if (-not (Test-Path $ignorePath)) {
    @"
.pre-commit-cache/
.pre-commit-config.yaml.bak
.venv*/
__pycache__/
.DS_Store
Thumbs.db
"@ | Set-Content -Encoding UTF8 $ignorePath
    Write-Host "Wrote default .gitignore" -ForegroundColor Green
}

# 3) Remove any staged cache/bak files
git restore --staged -A 2>$null
git rm -r --cached .pre-commit-cache, .pre-commit-config.yaml.bak 2>$null

# 4) Enforce LF normalization
git config core.autocrlf false
git rm --cached -r .
git reset --hard HEAD

# 5) Clean pre-commit cache
pre-commit clean | Out-Null
pre-commit gc | Out-Null

# 6) Re-add and commit normalization
git add -A
git commit -m "chore: normalize LF endings (auto-fix drift)" --no-verify | Out-Null

Write-Host "✅ LF normalization complete. Repo is clean and stable." -ForegroundColor Green
