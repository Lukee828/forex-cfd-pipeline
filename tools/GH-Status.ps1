[CmdletBinding()]
param([Parameter(ValueFromPipeline=$true)] [object]$PR)

$ErrorActionPreference = "Stop"
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw "GitHub CLI (gh) not found" }

function Get-PrObject {
  param([object]$Input)
  if ($Input -is [int]) {
    return (gh pr view $Input --json number,title,state,headRefName,url | ConvertFrom-Json)
  }
  if ($Input -and $Input.PSObject.Properties['number']) {
    $n = [int]$Input.number
    return (gh pr view $n --json number,title,state,headRefName,url | ConvertFrom-Json)
  }
  $branch = (git rev-parse --abbrev-ref HEAD).Trim()
  $open = gh pr list --state open --head $branch --json number,title,state,headRefName,url | ConvertFrom-Json
  if ($open -is [array]) { return $open[0] }
  if ($open) { return $open }
  throw "No open PR found for branch '$branch'."
}

$pr = Get-PrObject -Input $PR

$runs = gh run list --branch $pr.headRefName `
  --json databaseId,name,status,conclusion,createdAt,workflowName,url `
  -L 10 | ConvertFrom-Json

"`nPR #$($pr.number) [$($pr.state)]"
$pr.title
$pr.url
"Head: $($pr.headRefName)`n"

if (-not $runs) { "No recent workflow runs for branch '$($pr.headRefName)'."; return }

"{0,-26} {1,-10} {2,-12} {3,-20} {4}" -f "Workflow","Status","Conclusion","Created(UTC)","URL"
"{0,-26} {1,-10} {2,-12} {3,-20} {4}" -f ("-"*26),("-"*10),("-"*12),("-"*20),("-"*24)
foreach ($r in $runs) {
  $created = ([DateTime]$r.createdAt).ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss")
  "{0,-26} {1,-10} {2,-12} {3,-20} {4}" -f $r.workflowName, $r.status, ($r.conclusion ?? "-"), $created, $r.url
}
