param([string]$RunPath)

$ErrorActionPreference = "Stop"
$tag = "v{0}" -f (Get-Date -Format "yyyy.MM.dd.HHmmss")
Write-Host "Auto tag: $tag"

$pub = Join-Path $PSScriptRoot 'Publish-Release.ps1'
pwsh -NoProfile -File $pub -Tag $tag -RunPath $RunPath
