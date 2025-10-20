[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$root = (git rev-parse --show-toplevel 2>$null)
if (-not $root) { throw "Not a git repo." }
$lab       = Join-Path $root "ai_lab"
$statePath = Join-Path $lab  "state.json"
$manifest  = Join-Path $lab  "session_manifest.csv"
$report    = Join-Path $lab  "audit_report.md"

function Get-Hash([string]$txt) {
    $sha = [System.Security.Cryptography.SHA1]::Create()
    ($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($txt)) | ForEach-Object { $_.ToString("x2") }) -join ""
}

$issues = New-Object System.Collections.Generic.List[string]

# --- state.json checks ---
if (-not (Test-Path $statePath)) {
    $issues.Add("Missing state.json")
} else {
    $raw = Get-Content $statePath -Raw
    try { $st = $raw | ConvertFrom-Json } catch { $issues.Add("state.json not valid JSON: $($_.Exception.Message)"); $st = $null }
    if ($st) {
        $saved = $st.hash
        $st.hash = ""
        $calc = Get-Hash ($st | ConvertTo-Json -Depth 10)
        if ($saved -and $calc -ne $saved) { $issues.Add("state.json hash mismatch (calc $calc != saved $saved)") }
        if (-not $st.branch) { $issues.Add("state.json missing branch") }
        if (-not $st.commit) { $issues.Add("state.json missing commit") }
        else {
            $null = git rev-parse --verify $st.commit 2>$null
            if ($LASTEXITCODE -ne 0) { $issues.Add("state.commit not found in repo: $($st.commit)") }
        }
    }
}

# --- manifest checks ---
if (-not (Test-Path $manifest)) {
    $issues.Add("Missing session_manifest.csv")
} else {
    $lines = Get-Content $manifest
    if ($lines.Count -lt 2) { $issues.Add("Manifest has no entries") }
    foreach ($line in $lines | Select-Object -Skip 1) {
        if (-not $line) { continue }
        $parts = $line -split ",", 9
        if ($parts.Count -lt 9) { $issues.Add("Malformed manifest row: $line"); continue }
        $logPath = $parts[8]
        if (-not (Test-Path $logPath)) { $issues.Add("Missing session log file: $logPath") }
    }
}

# --- build report with normalized LF and single trailing newline ---
$newReport = @"
# Audit Report
UTC: $((Get-Date).ToUniversalTime().ToString("o"))
Repo: $root

## Findings
$( if ($issues.Count) { ($issues | ForEach-Object { "- $_" }) -join "`n" } else { "- OK: no issues found" } )
"@
$newReport = ($newReport -replace "`r`n", "`n")
if (-not $newReport.EndsWith("`n")) { $newReport += "`n" }

$oldReport = if (Test-Path $report) { (Get-Content $report -Raw) -replace "`r`n", "`n" } else { "" }
if ($oldReport -ne $newReport) {
    # Write without adding an extra newline (we already ensured one)
    Set-Content -Encoding UTF8 -Path $report -Value $newReport -NoNewline
}

if ($issues.Count) {
    Write-Host "Audit: issues found -> $report" -ForegroundColor Yellow
    exit 1
} else {
    Write-Host "Audit: OK -> $report" -ForegroundColor Green
    exit 0
}

# (Keep a final newline in THIS .ps1 file so end-of-file-fixer is happy)
