param(
  [Parameter(Mandatory=$true)][string]$PatchString,
  [string]$BranchName = "feature/v0.1.2-spine",
  [string]$CommitMsg  = "v0.1.2 spine: apply patch",
  [switch]$Push
)
$ErrorActionPreference = "Stop"

if (-not (Test-Path ".git")) { throw "Not a git repo: $(Get-Location)" }
git rev-parse --git-dir *> $null

$cur = (git rev-parse --abbrev-ref HEAD).Trim()
if ($cur -ne $BranchName) {
  if (git branch --list $BranchName) { git checkout $BranchName } else { git checkout -b $BranchName }
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = ".\.backup\$stamp"
New-Item -ItemType Directory -Force -Path $backupDir *> $null
$backupTargets = @("portfolio.py","backtest.py","walkforward.py","*.ps1","*.psm1")
foreach ($pattern in $backupTargets) {
  Get-ChildItem -Path . -Recurse -File -Filter $pattern | ForEach-Object {
    $rel  = $_.FullName.Substring((Get-Location).Path.Length + 1)
    $dest = Join-Path $backupDir $rel
    New-Item -ItemType Directory -Force -Path (Split-Path $dest) *> $null
    Copy-Item $_.FullName $dest -Force
  }
}

$patchPath = Join-Path $env:TEMP ("repo_patch_" + $stamp + ".diff")
$PatchString | Out-File -FilePath $patchPath -Encoding utf8

git apply --check $patchPath
git apply $patchPath

git add -A
Write-Host "`n=== STAGED DIFF ===" -ForegroundColor Yellow
git diff --cached

# --- disable git pager and skip .backup diffs ---
$env:GIT_PAGER = "cat"

# when showing staged diff, ignore .backup folder for readability
Write-Host "`n=== STAGED DIFF (excluding .backup) ===" -ForegroundColor Yellow
git diff --cached -- . ":(exclude).backup/*"

git commit -m $CommitMsg

if ($Push) {
  $null = & git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>$null
  if ($LASTEXITCODE -ne 0) { git push -u origin $BranchName } else { git push }
}

Write-Host ("Done. Branch: {0}  Commit: {1}" -f $BranchName, (git rev-parse --short HEAD)) -ForegroundColor Green
