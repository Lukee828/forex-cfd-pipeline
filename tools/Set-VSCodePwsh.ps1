param()
$ErrorActionPreference = "Stop"

# Locate pwsh.exe
$pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source
if (-not $pwsh) {
    Write-Error "pwsh.exe not found. Install PowerShell 7 from https://aka.ms/PowerShell-Release"
    exit 1
}

# VS Code user settings path
$settings = Join-Path $env:APPDATA 'Code\User\settings.json'
$settingsDir = Split-Path $settings -Parent
if (-not (Test-Path $settingsDir)) {
    New-Item -ItemType Directory -Force -Path $settingsDir | Out-Null
}

# Read existing JSON (or start fresh)
$jsonText = if (Test-Path $settings) { Get-Content $settings -Raw } else { '{}' }
try {
    $json = $jsonText | ConvertFrom-Json -ErrorAction Stop
} catch {
    Write-Warning "settings.json is not valid JSON; starting fresh."
    $json = New-Object psobject
}

# Ensure nested keys exist
if (-not $json.'terminal.integrated.profiles') {
    $json | Add-Member -NotePropertyName 'terminal.integrated.profiles' -NotePropertyValue @{}
}
$profiles = $json.'terminal.integrated.profiles'
if ($profiles -isnot [hashtable]) { $profiles = @{}; $json.'terminal.integrated.profiles' = $profiles }

# Add a profile for PowerShell 7
$profiles.'PowerShell 7' = @{ path = $pwsh }

# Make it the default terminal on Windows
$json.'terminal.integrated.defaultProfile.windows' = 'PowerShell 7'

# Save back
$json | ConvertTo-Json -Depth 64 | Set-Content -Encoding UTF8 $settings

Write-Host "Configured VS Code to use pwsh by default."
Write-Host "pwsh path: $pwsh"
Write-Host "settings.json: $settings"

