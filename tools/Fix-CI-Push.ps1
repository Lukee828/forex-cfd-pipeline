#requires -Version 7
param()

$ErrorActionPreference='Stop'
$utf8 = [System.Text.UTF8Encoding]::new($false)

function Get-VenvBin([string]$exe){
  $p = Join-Path $PWD ".venv\\Scripts\\$exe"
  if(Test-Path $p){ return $p } else { return $null }
}

function Normalize-Newlines([string]$text){
  return ($text -replace "`r?`n","`n")
}

function Ensure-ZeroTouch {
  $zt = 'tools/Zero-Touch.ps1'
  if(-not (Test-Path $zt)){
    Write-Host "No $zt found; skipping Zero-Touch fixes." -ForegroundColor Yellow
    return
  }

  $orig = Normalize-Newlines (Get-Content -LiteralPath $zt -Raw -Encoding UTF8)
  $text = $orig
  $changed = $false

  # --- 1) Ensure header at the very top: #requires, [CmdletBinding()], param()
  # Keep a leading shebang/comment block if present
  $lead = ''
  $leadMatch = [regex]::Match($text, '^(?<lead>(?:[#!].*\n)+)')
  if($leadMatch.Success){
    $lead = $leadMatch.Groups['lead'].Value
    $text = $text.Substring($lead.Length)
  }

  # Strip any stray header bits anywhere in body
  $text = [regex]::Replace($text, '^\s*\[CmdletBinding(?:\([^\)]*\))?\]\s*\n?', '', 'Multiline')
  $text = [regex]::Replace($text, '^\s*param\s*\(\s*\)\s*\n?', '', 'Multiline')
  $text = [regex]::Replace($text, '^\s*#requires[^\n]*\n?', '', 'Multiline')

  $header = "#requires -Version 7`n[CmdletBinding()]`nparam()`n"
  $rebuilt = $lead + $header + $text
  if($rebuilt -ne $orig){
    [IO.File]::WriteAllText($zt, $rebuilt, $utf8)
    $changed = $true
  }

  # Reload current text
  $cur = Normalize-Newlines (Get-Content -LiteralPath $zt -Raw -Encoding UTF8)

  # --- 2) Inject Try-Dispatch helper (quiet & opt-in via GIT_RD=1)
  if($cur -notmatch '(?m)^\s*function\s+Try-Dispatch\b'){
    $inject = @"
function Try-Dispatch {
  param([Parameter(Mandatory)][string]`$Workflow, [Parameter(Mandatory)][string]`$Ref)
  if (`$env:GIT_RD -ne '1') { Write-Host '[ZT] Remote dispatch disabled (set GIT_RD=1 to enable)' -ForegroundColor DarkGray; return }
  try {
    # Only dispatch if the workflow declares workflow_dispatch
    `$view = (& gh workflow view `$Workflow --yaml 2>`$null)
    if (-not `$view -or `$view -notmatch '(?m)^\s*workflow_dispatch:\s*$') {
      Write-Host "[ZT] Skipping '`$Workflow' (no workflow_dispatch)" -ForegroundColor DarkGray
      return
    }
    $null = & gh workflow run `$Workflow --ref `$Ref 2>`$null
    Write-Host "[ZT] Dispatched `$Workflow on `$Ref" -ForegroundColor DarkGray
  } catch {
    Write-Host "[ZT] Quietly skipped dispatch for '`$Workflow' ($($_.Exception.Message))" -ForegroundColor DarkGray
  }
}
"@
    # put right after param()
    $cur = [regex]::Replace($cur, '(?ms)(^.*?param\(\)\s*\n)', { param($m) $m.Groups[1].Value + $inject })
    [IO.File]::WriteAllText($zt, $cur, $utf8)
    $changed = $true
  }

  # --- 3) Rewrite raw "gh workflow run … --ref $branch" calls to Try-Dispatch
  $cur = Normalize-Newlines (Get-Content -LiteralPath $zt -Raw -Encoding UTF8)
  $pat = '(?m)^\s*gh\s+workflow\s+run\s+(".*?"|\S+)\s+--ref\s+\$branch\s*$'
  if([regex]::IsMatch($cur, $pat)){
    $cur = [regex]::Replace($cur, $pat, { param($m) "Try-Dispatch " + $m.Groups[1].Value + " `$branch" })
    [IO.File]::WriteAllText($zt, $cur, $utf8)
    $changed = $true
  }

  if($changed){
    git add -- $zt | Out-Null
    git commit -m "fix(Zero-Touch): canonical header + quiet Try-Dispatch + safe dispatch rewrite" | Out-Null
    Write-Host "Zero-Touch.ps1 healed." -ForegroundColor Green
  } else {
    Write-Host "Zero-Touch.ps1 already healthy." -ForegroundColor DarkGray
  }
}

function Run-PreCommit-Autofix {
  $pc  = Get-VenvBin 'pre-commit.exe'
  $pip = Get-VenvBin 'pip.exe'
  if(-not $pc -and $pip){
    & $pip install pre-commit -q
    $pc = Get-VenvBin 'pre-commit.exe'
  }
  if($pc){
    Write-Host "Running pre-commit -a to apply autofixes..." -ForegroundColor Cyan
    & $pc run -a | Write-Host
    $dirty = git status --porcelain
    if(-not [string]::IsNullOrWhiteSpace($dirty)){
      git add -A | Out-Null
      git commit -m "chore(pre-commit): apply EOF/trailing-whitespace fixes" | Out-Null
      Write-Host "Committed pre-commit autofixes." -ForegroundColor Green
    } else {
      Write-Host "No pre-commit changes to commit." -ForegroundColor DarkGray
    }
  } else {
    Write-Host "pre-commit not available (and no .venv pip); skipping autofix." -ForegroundColor Yellow
  }
}

Ensure-ZeroTouch
Run-PreCommit-Autofix

try { git push | Out-Null; Write-Host "`n✅ CI/push healed." -ForegroundColor Green }
catch { Write-Warning "Push had no changes or failed: $($_.Exception.Message)" }
