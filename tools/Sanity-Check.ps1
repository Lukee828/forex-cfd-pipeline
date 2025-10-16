param([string]$Milestone = "v1.1")
$ErrorActionPreference='Stop'

Write-Host "== GIT =="
$inside = git rev-parse --is-inside-work-tree 2>$null
if (-not $inside -or $inside.Trim() -ne 'true') { throw "Not inside a git repo." }
$dirty = git status --porcelain
if ($dirty) { Write-Host "Uncommitted changes present:"; $dirty | Out-Host } else { Write-Host "Working tree clean" }

$ver = git describe --tags --always 2>$null
if (-not $ver) { $ver = (git rev-parse --short HEAD) }
Write-Host ("Version: " + $ver)

Write-Host "`n== GH CLI =="
gh --version | Out-Host
gh auth status | Out-Host

Write-Host "`n== REPO =="
$repo = gh repo view --json nameWithOwner | ConvertFrom-Json
Write-Host ("Repo: " + $repo.nameWithOwner)

Write-Host "`n== MILESTONE & LABELS =="
$ms = gh milestone list --json title,number | ConvertFrom-Json | Where-Object { $_.title -eq $Milestone }
if (-not $ms) {
  Write-Host ("Milestone '" + $Milestone + "' not found -> creating")
  gh milestone create $Milestone --description "Autocreated by sanity check" | Out-Null
  $ms = gh milestone list --json title,number | ConvertFrom-Json | Where-Object { $_.title -eq $Milestone }
}
Write-Host ("Milestone OK: " + $ms.title + " (#" + $ms.number + ")")

$required = @("type:feat","type:ci","type:docs","area:strategy","area:risk","area:ops","priority:high","priority:med")
$existing = gh label list --json name | ConvertFrom-Json | ForEach-Object { $_.name }
$missing = $required | Where-Object { $_ -notin $existing }
if ($missing) {
  Write-Host ("Creating missing labels: " + ($missing -join ", "))
  foreach($l in $missing){ gh label create $l --color 0366d6 --description $l 2>$null }
} else {
  Write-Host "All required labels present"
}

Write-Host "`n== OPEN ISSUES (milestone) =="
$issues = gh issue list --milestone $Milestone --state open --limit 100 --json number,title | ConvertFrom-Json | Sort-Object number
if ($issues) {
  $issues | ForEach-Object { "{0,5}  {1}" -f $_.number, $_.title } | Out-Host
  Write-Host ("Total: " + $issues.Count)
} else {
  Write-Host "None"
}

Write-Host "`n== KEY FILES =="
$key = @(".github/workflows/ci.yml","tools/Run-FullQA.ps1",".pre-commit-config.yaml")
$miss = $key | Where-Object { -not (Test-Path $_) }
if ($miss) { Write-Host ("Missing: " + ($miss -join ", ")) } else { Write-Host "All key files present" }

Write-Host "`nSanity check complete."
