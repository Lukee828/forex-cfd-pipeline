# tools/Heartbeat.ps1 — write a one-line status every 10 min
while ($true) {
  $root = (git rev-parse --show-toplevel) 2>$null
  if ($root) {
    $ai = Join-Path $root 'ai_lab'
    $hb = Join-Path $ai 'heartbeat.log'
    $branch = (git rev-parse --abbrev-ref HEAD)
    $commit = (git rev-parse --short HEAD)
    $ts = (Get-Date).ToUniversalTime().ToString('s') + 'Z'
    "$ts | $branch@$commit" | Add-Content -Encoding UTF8 $hb
  }
  Start-Sleep -Seconds 600
}
