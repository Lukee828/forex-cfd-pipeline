param(
  [string]$PythonExe = ".\.venv311\Scripts\python.exe",
  [string]$OutFile   = "$PWD\docs\CLI.md"
)
$ErrorActionPreference = "Stop"

# Ensure alpha_factory imports from ./src
if (-not $env:PYTHONPATH) { $env:PYTHONPATH = (Resolve-Path .\src).Path }

# Top-level help
$top = & $PythonExe -m alpha_factory.registry_cli -h

# Extract the {init,register,...} line and capture content between braces
$subsLine = ($top -split "`r?`n" | Where-Object { $_ -match '^\s*\{[^}]+\}\s*$' } | Select-Object -First 1)
$subs = @()
if ($subsLine -and ($subsLine -match '^\s*\{(?<list>[^}]+)\}\s*$')) {
  $subs = $matches['list'].Split(',') | ForEach-Object { $_.Trim() }
}

# Build markdown
$md = @()
$md += '# Alpha Registry CLI'
$md += ''
$md += '> Generated from `alpha_factory.registry_cli` help output.'
$md += ''
$md += '## Top-level'
$md += ''
$md += '```text'
$md += $top
$md += '```'
$md += ''
$md += '## Subcommands'
$md += ''

foreach ($s in $subs) {
  $md += "### $s"
  $md += ''
  $md += '```text'
  $md += (& $PythonExe -m alpha_factory.registry_cli $s -h)
  $md += '```'
  $md += ''
}

# Write (UTF-8 no BOM, LF)
$null = New-Item -ItemType Directory -Force -Path (Split-Path $OutFile)
[IO.File]::WriteAllText($OutFile, (($md -join "`n") + "`n"), [Text.UTF8Encoding]::new($false))
Write-Output "OK - wrote $OutFile"
