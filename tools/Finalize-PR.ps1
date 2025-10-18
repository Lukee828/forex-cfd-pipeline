#requires -Version 7.0
param()
param([int]$Number)
$ErrorActionPreference='Stop'
for($i=0;$i -lt 20;$i++){
  $j = gh pr view $Number --json state,mergeable,mergeStateStatus -q '{s:.state,m:.mergeable,g:.mergeStateStatus}' 2>$null
  if(-not $j){ Start-Sleep 2; continue }
  if($j.s -eq 'MERGED'){ break }
  try { gh pr merge $Number --squash --delete-branch --auto; break } catch { Start-Sleep 3 }
}

