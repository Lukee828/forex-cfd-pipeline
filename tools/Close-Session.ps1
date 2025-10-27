param(
  [string]$Repo = "C:\Users\speed\Desktop\forex-standalone",
  [string]$Status = "closed",
  [string]$Note = ""
)

$ErrorActionPreference = "Stop"
Set-Location $Repo

$sp = "ai_lab/state.json"
if (!(Test-Path $sp)) { throw "state.json not found at $sp" }

$sha = (git rev-parse --short=7 HEAD).Trim()
$s = Get-Content $sp -Raw | ConvertFrom-Json -AsHashtable

# ensure latest_session keys
if (-not $s.ContainsKey("latest_session") -or $null -eq $s["latest_session"]) { $s["latest_session"] = @{} }
$ls = $s["latest_session"]
foreach ($k in @("utc","status","pytest","ai_guard","summary","log")) { if (-not $ls.ContainsKey($k)) { $ls[$k] = $null } }

# advance pointers
$s["commit"] = $sha
$s["last_synced"] = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
$ls["status"] = $Status
if (-not $ls.ContainsKey("end_utc") -or -not $ls["end_utc"]) { $ls["end_utc"] = $null }
$ls["end_utc"] = (Get-Date).ToUniversalTime().ToString("s") + "Z"

# persist state
$s | ConvertTo-Json -Depth 20 | Set-Content -Encoding UTF8 $sp
git add $sp | Out-Null
git commit -m ("ai_lab(session): {0} day; advance pointer to HEAD {1}" -f $Status,$sha) | Out-Null

# append a line to session log if present
if ($ls["log"] -and (Test-Path $ls["log"])) {
  $line = ("closed_utc: {0} | status: {1}" -f $ls["end_utc"], $Status)
  if ($Note) { $line = $line + (" | note: {0}" -f $Note) }
  Add-Content -Encoding UTF8 -Path $ls["log"] -Value $line
  git add $ls["log"] | Out-Null
  git commit -m ("ai_lab(session): annotate log ({0})" -f $Status) | Out-Null
}

# ensure state hash is stable (writer runs here just in case)
pwsh -NoProfile -File tools/Update-StateHash.ps1
git add ai_lab/state.json | Out-Null
git commit -m "ci: refresh state hash" | Out-Null

# push (pre-push is verify-only)
git push origin main | Out-Null
Write-Host ("✔ Session closed as {0} at {1} (HEAD {2})" -f $Status,(Get-Date).ToString("s"),$sha) -ForegroundColor Green
