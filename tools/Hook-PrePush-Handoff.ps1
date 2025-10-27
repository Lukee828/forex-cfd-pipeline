param()

$ErrorActionPreference = "Stop"

# Run the hasher once (it may *try* to write); we immediately detect & forbid that at push-time.
pwsh -NoProfile -File tools/Update-StateHash.ps1

# If the updater modified ai_lab/state.json, block push with a clear message.
$changed = (git diff --name-only -- ai_lab/state.json)
if ($changed) {
  Write-Host "❌ state.json hash was stale at push-time." -ForegroundColor Red
  Write-Host "Run: pwsh -File tools/Update-StateHash.ps1 ; git add ai_lab/state.json ; git commit -m 'ci: refresh state hash' ; git push" -ForegroundColor Yellow
  exit 1
}

Write-Host "✔ state.json hash OK (verify-only)" -ForegroundColor Green
exit 0
