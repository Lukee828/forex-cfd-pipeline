param([int]$SinceHours = 24)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = (git rev-parse --show-toplevel)
$ai = Join-Path $root 'ai_lab'
$man = Join-Path $ai 'session_manifest.csv'
$statePath = Join-Path $ai 'state.json'

if (Test-Path $statePath) {
  $state = (Get-Content $statePath -Raw | ConvertFrom-Json -AsHashtable)
  Write-Host ("State → branch={0} commit={1} feature={2} ai_guard={3}" -f $state.branch,$state.commit,$state.active_feature,$state.ai_guard)
}

if (Test-Path $man) {
  $rows = Get-Content $man | Select-Object -Skip 1 | Where-Object { $_ }
  if ($rows) {
    $last = $rows[-1]; $cols = $last.Split(',')
    $ts,$branch,$feature,$commit,$ai,$py,$st,$sum,$log = $cols[0..8]
    Write-Host "Latest session → $ts | $branch | $feature | $st | $ai/$py" -ForegroundColor Cyan
    if (Test-Path $log) {
      Write-Host "Log head: $log" -ForegroundColor DarkCyan
      Get-Content $log | Select-Object -First 40 | ForEach-Object { $_ }
    }
  }
} else {
  Write-Host "No session_manifest.csv yet — run Init-ChatOps + Session-Commit." -ForegroundColor Yellow
}

$since = (Get-Date).AddHours(-$SinceHours)
Write-Host ("Recent commits (since {0}):" -f $since) -ForegroundColor Yellow
& git log --since="$($since.ToString('o'))" --pretty=format:"%C(auto)%h %ad %Cgreen%an%Creset %s" --date=short -n 50
