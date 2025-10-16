#requires -Version 7
[CmdletBinding()]
param(
  [switch]$DryRun = $false,
  [string]$Branch = $null,
  [int]$Tail = 120,
  [switch]$NoTrigger,
  [switch]$NoWatch
)

$ErrorActionPreference = 'Stop'

function Step([string]$Message, [ConsoleColor]$Color = [ConsoleColor]::Cyan) {
  $orig = $Host.UI.RawUI.ForegroundColor
  $Host.UI.RawUI.ForegroundColor = $Color
  Write-Host "• $Message"
  $Host.UI.RawUI.ForegroundColor = $orig
}

# Resolve branch name when not provided
if ([string]::IsNullOrWhiteSpace($Branch)) {
  try { $Branch = (git rev-parse --abbrev-ref HEAD).Trim() } catch { $Branch = '' }
}
if ([string]::IsNullOrWhiteSpace($Branch)) {
  throw "Could not determine current branch."
}

# ------------- helpers -------------
function Try-Dispatch {
  param(
    [Parameter(Mandatory)] [string]$Workflow,  # e.g. ".github/workflows/lint.yml"
    [Parameter(Mandatory)] [string]$Ref
  )
  if ($env:GIT_RD -ne '1') {
    Write-Host "[ZT] Remote dispatch disabled (GIT_RD != 1)" -ForegroundColor DarkGray
    return
  }
  try {
    $view = (& gh workflow view $Workflow --yaml 2>$null)
    if (-not $view -or $view -notmatch '(?m)^\s*workflow_dispatch:\s*$') {
      Write-Host "[ZT] Skipping '$Workflow' (no workflow_dispatch)" -ForegroundColor DarkGray
      return
    }
    $null = & gh workflow run $Workflow --ref $Ref 2>$null
    Write-Host "[ZT] Dispatched $Workflow on $Ref" -ForegroundColor DarkGray
  } catch {
    Write-Host "[ZT] Quietly skipped dispatch for '$Workflow' ($($_.Exception.Message))" -ForegroundColor DarkGray
  }
}

function Ensure-FileContent {
  param(
    [Parameter(Mandatory)] [string]$File,
    [Parameter(Mandatory)] [string]$Content
  )
  $existing = if (Test-Path $File) { Get-Content -LiteralPath $File -Raw -Encoding UTF8 } else { '' }
  if ($existing -ne $Content) {
    $dir = Split-Path $File
    if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    [IO.File]::WriteAllText($File, ($Content -replace "`r?`n","`n"), [System.Text.UTF8Encoding]::new($false))
    return $true
  }
  return $false
}

# Track whether we changed anything to commit/push
$script:Changed = $false
function Mark-Changed([string]$Path) { git add -- $Path | Out-Null; $script:Changed = $true }

# ------------- 1) Normalize .gitattributes -------------
$gattrPath = '.gitattributes'
$needed = @(
  '* text=auto',
  '*.yml  text eol=lf',
  '*.yaml text eol=lf',
  '*.py   text eol=lf',
  '*.sh   text eol=lf',
  '*.ps1  text eol=lf',
  '*.ipynb -text'
)
$cur = (Test-Path $gattrPath) ? (Get-Content -LiteralPath $gattrPath -Encoding UTF8) : @()
$missing = $needed | Where-Object { $_ -notin $cur }
if ($missing) {
  Step "Updating .gitattributes"
  if (-not $DryRun) {
    $content = @()
    if ($cur.Count) { $content += $cur; if ($content[-1] -ne '') { $content += '' } }
    $content += '# separator'
    $content += $missing
    Set-Content -LiteralPath $gattrPath -Value $content -Encoding UTF8
  }
  Mark-Changed $gattrPath
} else {
  Step ".gitattributes OK" 'DarkGray'
}

# ------------- 2) Ensure watcher script -------------
$watchPath = 'tools/Dispatch-And-Watch.ps1'
# [ZT-FIX] removed watcher template block
