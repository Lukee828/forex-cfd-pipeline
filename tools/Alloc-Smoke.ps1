Param([ValidateSet("ewma","equal","bayes")]$Mode="ewma")
$ErrorActionPreference="Stop"
$root=(& git rev-parse --show-toplevel 2>$null); if(-not $root){$root=(Get-Location).Path}
$out=Join-Path $root "artifacts/allocations"; if(-not (Test-Path $out)){New-Item -ItemType Directory -Force -Path $out|Out-Null}
pwsh -File tools/Export-Allocations.ps1 -Mode $Mode | Out-Host
$wf=".github/workflows/meta-alloc-smoke.yml"
gh workflow run $wf | Out-Host
$rid=$null; for($i=0;$i -lt 90 -and -not $rid;$i++){ Start-Sleep 1; $rid=gh run list --workflow $wf -L 1 --json databaseId --jq '.[0].databaseId' 2>$null }
if(-not $rid){ throw "No run appeared for $wf." }
$deadline=(Get-Date).AddMinutes(3)
do{ $m=gh run view $rid --json status,conclusion,url | ConvertFrom-Json; "Run: $($m.url) | status=$($m.status) | conclusion=$($m.conclusion)"; if($m.status -in @("completed","cancelled")){break}; Start-Sleep 3 } while((Get-Date) -lt $deadline)
$dest=Join-Path $root "artifacts/ci-meta/$rid"; if(Test-Path $dest){Remove-Item $dest -Recurse -Force}; New-Item -ItemType Directory -Force -Path $dest|Out-Null
gh run download $rid --name allocations --dir $dest 2>$null
Write-Host "`n== Local latest.csv ==" -ForegroundColor Cyan
$latest=Join-Path $out "latest.csv"; if(Test-Path $latest){ Get-Content $latest } else { Write-Warning "No latest.csv (local)" }
Write-Host "`n== CI artifact(s) ==" -ForegroundColor Cyan
Get-ChildItem $dest -Recurse | Format-Table -Auto
Write-Host "`nDone." -ForegroundColor Green
