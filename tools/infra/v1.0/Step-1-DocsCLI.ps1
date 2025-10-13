param(
  [Parameter(Mandatory=$true)][string]$PythonExe,
  [Parameter(Mandatory=$true)][string]$RegistryDb,
  [Parameter(Mandatory=$true)][string]$OutFile
)
$ErrorActionPreference = "Stop"

function Invoke-Cli {
  param([string[]]$Argv)
  $txt = & $PythonExe @Argv 2>&1
  if ($LASTEXITCODE -ne 0) {
    throw ("CLI failed: {0} {1}`n{2}" -f $PythonExe, ($Argv -join ' '), ($txt | Out-String))
  }
  ($txt | Out-String).TrimEnd()
}

Write-Host "[INFO] Capturing CLI help"
$topHelp = Invoke-Cli @('-m','alpha_factory.registry_cli','-h')

# discover subcommands from the line like: {init,register,...}
$subcmds = @()
foreach ($line in ($topHelp -split "`r?`n")) {
  if ($line -match '^\s*\{([^}]+)\}') {
    $subcmds = $Matches[1].Split(',') | ForEach-Object { $_.Trim() }
    break
  }
}
if (-not $subcmds) { throw "Failed to discover subcommands from top-level help." }

# capture -h for each subcommand
$helps = @{}
foreach ($cmd in $subcmds) {
  $helps[$cmd] = Invoke-Cli @('-m','alpha_factory.registry_cli', $cmd, '-h')
}

# sanity: export should have --theme {light,dark}
if (-not $helps.ContainsKey('export')) { throw "'export' subcommand missing." }
if (-not ($helps['export'] -match '--theme\s+\{light,dark\}')) {
  throw "'--theme {light,dark}' missing in 'export -h'."
}

# build markdown using a plain string array (single quotes to avoid interpolation)
$md = @()
$md += '# Alpha Registry CLI'
$md += ''
$md += '> Generated from `alpha_factory.registry_cli` help output.'
$md += ''
$md += '## Top-level'
$md += ''
$md += '```text'
$md += $topHelp
$md += '```'
$md += ''
$md += '## Subcommands'
$md += ''
foreach ($cmd in ($subcmds | Sort-Object)) {
  $md += ('### {0}' -f $cmd)
  $md += ''
  $md += '```text'
  $md += $helps[$cmd]
  $md += '```'
  $md += ''
}

# write file (UTF-8 LF)
$null = New-Item -ItemType Directory -Force -Path (Split-Path $OutFile) | Out-Null
$mdText = ($md -join "`n") -replace "`r?`n","`n"
[IO.File]::WriteAllText($OutFile, $mdText, [Text.UTF8Encoding]::new($false))
Write-Host ("[OK]   Wrote {0}" -f $OutFile) -ForegroundColor Green
