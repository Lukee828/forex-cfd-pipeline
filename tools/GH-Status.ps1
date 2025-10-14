param([int]$Limit = 20)

Write-Host "== Repo sync ==" -ForegroundColor Cyan
git status
git log -1 --oneline

Write-Host "`n== Open PRs ==" -ForegroundColor Cyan
gh pr list --state open --limit $Limit

Write-Host "`n== Merged PRs (recent) ==" -ForegroundColor Cyan
gh pr list --state merged --limit $Limit

Write-Host "`n== Local branches merged into origin/main ==" -ForegroundColor Cyan
git branch --merged origin/main

