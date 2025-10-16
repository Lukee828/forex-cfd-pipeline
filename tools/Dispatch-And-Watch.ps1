param([string]\feat/v1.0-infra-feature-store='feat/v1.0-infra-feature-store',[int]\120=80)
Write-Host "
Watching workflows on branch: \feat/v1.0-infra-feature-store (last \120 lines)" -ForegroundColor Cyan
try { \ = gh run list --branch \feat/v1.0-infra-feature-store -L 4 --json databaseId,workflowName,status,conclusion,url | ConvertFrom-Json } catch { \=@() }
foreach(\ in \){
  "
--- {0} ({1}) {2}/{3} ---
{4}" -f \.workflowName,\.databaseId,\.status,(\.conclusion ?? '-'),\.url
  try { gh run view \.databaseId --log | Select-Object -Last \120 } catch { Write-Host "[no log yet]" -ForegroundColor DarkGray }
}