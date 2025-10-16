param(
  [Parameter(Position=0)]
  [string]$Tag,                                 # e.g. v1.0.3
  [Parameter(Position=1)]
  [string]$PR,                                  # PR number or full URL; if omitted, uses latest merged into -Branch
  [string]$Branch = "main",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Resolve-PrNumber([string]$Input){
  if ([string]::IsNullOrWhiteSpace($Input)) { return $null }
  if ($Input -match '/pull/(\d+)') { return [int]$Matches[1] }
  if ($Input -as [int]) { return [int]$Input }
  throw "Could not parse PR identifier from: $Input"
}

function Get-LatestMergedPr([string]$Base){
  $list = gh pr list --state merged --base $Base --limit 1 --search "sort:updated-desc" `
          --json number,mergedAt,title,url | ConvertFrom-Json
  if (-not $list -or -not $list[0]) { throw "No merged PRs found into base '$Base'." }
  return $list[0].number
}

function Ensure-CommitPresent([string]$Sha){
  git fetch origin $using:Branch --tags | Out-Null
  git cat-file -e ($Sha + "^{commit}") 2>$null
}

# 1) Determine PR
$prNum = Resolve-PrNumber $PR
if (-not $prNum) { $prNum = Get-LatestMergedPr $Branch }

# 2) Inspect PR and validate it is merged into target base
$info = gh pr view $prNum --json state,mergeCommit,title,body,number,baseRefName,headRefName,mergedAt,url | ConvertFrom-Json
if ($info.state -ne "MERGED") { throw "PR #$($info.number) is not merged (state=$($info.state))." }
if ($info.baseRefName -ne $Branch) { throw "PR #$($info.number) base is '$($info.baseRefName)', expected '$Branch'." }
$sha = $info.mergeCommit
if (-not $sha) { throw "No merge commit SHA for PR #$($info.number)." }

# 3) Choose tag name if not provided
if (-not $Tag) {
  # simple monotonic fallback: v1.0.<N>-auto where N = existing count+1
  $existing = (git tag --list "v1.0.*" | Measure-Object).Count
  $Tag = "v1.0.{0}-auto" -f ($existing + 1)
}

# 4) Safety checks
if ((git tag --list $Tag)) { throw "Tag '$Tag' already exists." }
Ensure-CommitPresent $sha

# 5) Compose message
$nl = [Environment]::NewLine
$msg = "Release $Tag$nl$nl$($info.title)$nl$nl$($info.body)"

Write-Host "Target:"
Write-Host "  PR:    #$($info.number) ($($info.url))"
Write-Host "  Base:  $($info.baseRefName)"
Write-Host "  Head:  $($info.headRefName)"
Write-Host "  Merge: $sha"
Write-Host "  Tag:   $Tag"
if ($DryRun) {
  Write-Host "`n[DryRun] Would create annotated tag and push:"
  Write-Host "  git tag -a $Tag $sha -m <message>"
  Write-Host "  git push origin $Tag"
  exit 0
}

# 6) Create tag on the merge commit and push
git tag -a $Tag $sha -m $msg
git push origin $Tag

Write-Host "`nDone. Created and pushed tag '$Tag' at merge commit $sha."
