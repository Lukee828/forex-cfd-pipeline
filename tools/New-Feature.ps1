# ============================================================================
# New-Feature.ps1 — one-command feature workflow (auto PR + auto merge)
# ============================================================================

param(
    [Parameter(Mandatory=$true)]
    [string]$Branch,
    [Parameter(Mandatory=$true)]
    [string]$Title,
    [Parameter(Mandatory=$true)]
    [string]$Notes,
    [string]$Tag = ""
)

Write-Host "🔹 Switching to new branch: $Branch"
git switch -c $Branch 2>$null | Out-Null
git switch $Branch | Out-Null

Write-Host "🔹 Running pre-commit + pytest"
.\.venv\Scripts\pre-commit.exe run -a
.\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "❌ Tests failed; aborting." }

git add -A
git commit -m $Title
git push -u origin HEAD

# --- Create PR if missing ---------------------------------------------------
$existing = gh pr list --head $Branch --state open --json number -q '.[0].number'
if (-not $existing) {
    gh pr create --base main --head $Branch --title $Title --body $Notes
}
$pr = gh pr view --json number -q .number
Write-Host "🔹 PR #$pr created or exists"

# --- Wait for CI checks -----------------------------------------------------
Write-Host "⏳ Waiting for checks..."
do {
    $rollup = gh pr view $pr --json statusCheckRollup -q '.statusCheckRollup[].conclusion'
    if ($rollup -contains 'FAILURE') { throw "❌ A required check failed." }
    Start-Sleep -Seconds 5
} until ($rollup -and ($rollup -notcontains $null) -and ($rollup -notcontains 'PENDING'))
Write-Host "✅ Checks passed"

# --- Auto-merge -------------------------------------------------------------
gh pr merge $pr --squash --delete-branch --auto
Write-Host "✅ PR #$pr merged successfully"

# --- Tag + Release ----------------------------------------------------------
git switch main
git pull --ff-only

if (-not $Tag) {
    $ts = (Get-Date).ToString('yyyyMMdd-HHmm')
    $Tag = "v-next-$($Branch.Replace('/','-'))-$ts"
}
if (-not (git tag -l $Tag)) {
    git tag $Tag
    git push origin $Tag
}

Write-Host "✅ Tag created: $Tag"

$exists = gh release view $Tag --json tagName -q .tagName 2>$null
if (-not $exists) {
    gh release create $Tag `
        --title $Title `
        --notes $Notes `
        --latest
}
Write-Host "🏁 Release ready: $Tag"
