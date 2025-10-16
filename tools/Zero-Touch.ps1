#Requires -Version 7
[CmdletBinding()]
param(
  [string]$Branch = $(git rev-parse --abbrev-ref HEAD),
  [int]$Tail = 100,
  [switch]$NoTrigger,
  [switch]$NoWatch,
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
function Step($msg,[ConsoleColor]$c=[ConsoleColor]::Cyan){ $old=$Host.UI.RawUI.ForegroundColor; $Host.UI.RawUI.ForegroundColor=$c; Write-Host "• $msg"; $Host.UI.RawUI.ForegroundColor=$old }
function Changed($p){ git add $p | Out-Null; $script:__changed = $true }

# --- 0) Sanity ---
if(-not (Test-Path .git)){ throw "Run from repo root ('.git' not found)" }
if([string]::IsNullOrWhiteSpace($Branch)){ $Branch = $(git rev-parse --abbrev-ref HEAD) }

# --- 1) Normalize line-endings policy ---
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
if(Test-Path $gattrPath){
  $cur = Get-Content $gattrPath -Encoding UTF8
}else{
  $cur = @()
}
$missing = $needed | Where-Object { $_ -notin $cur }
if($missing){
  Step "Updating .gitattributes"
  if(-not $DryRun){ ($cur + '',''# separator'' + $missing) | Set-Content -Encoding UTF8 $gattrPath }
  Changed $gattrPath
}else{
  Step ".gitattributes OK" 'DarkGray'
}

# --- 2) Ensure tools/Dispatch-And-Watch.ps1 exists ---
$watchPath = 'tools/Dispatch-And-Watch.ps1'
if(-not (Test-Path $watchPath)){
  Step "Creating tools/Dispatch-And-Watch.ps1"
  $watch = @"
param([string]\$Branch='main',[int]\$Tail=80)
Write-Host "`nWatching workflows on branch: \$Branch (last \$Tail lines)" -ForegroundColor Cyan
try { \$rows = gh run list --branch \$Branch -L 4 --json databaseId,workflowName,status,conclusion,url | ConvertFrom-Json } catch { \$rows=@() }
foreach(\$r in \$rows){
  "`n--- {0} ({1}) {2}/{3} ---`n{4}" -f \$r.workflowName,\$r.databaseId,\$r.status,(\$r.conclusion ?? '-'),\$r.url
  try { gh run view \$r.databaseId --log | Select-Object -Last \$Tail } catch { Write-Host "[no log yet]" -ForegroundColor DarkGray }
}
"@
  if(-not $DryRun){ $watch | Set-Content -Encoding UTF8 $watchPath }
  Changed $watchPath
}else{
  Step "Watcher present" 'DarkGray'
}

# --- 3) Patch workflows (lint.yml, ci.yml) ---
$wfFiles = @('.github/workflows/lint.yml','.github/workflows/ci.yml') | Where-Object { Test-Path $_ }
foreach($wf in $wfFiles){
  Step "Patching $wf"
  $lines = Get-Content -LiteralPath $wf -Encoding UTF8
  $orig  = $lines.Clone()

  # 3a) Ensure on: workflow_dispatch
  if(-not ($lines -match '^\s*workflow_dispatch\s*:')){
    $idx = 0
    for($i=0;$i -lt $lines.Count;$i++){
      if($lines[$i] -match '^\s*on\s*:'){
        $idx = $i + 1
        $indent = ($lines[$i] -replace '^(\s*).*','$1') + '  '
        $insert = "$indent" + 'workflow_dispatch:'
        $lines = @($lines[0..($i)]) + @($insert) + @($lines[($i+1)..($lines.Count-1)])
        break
      }
    }
  }

  # 3b) Quiet Black + exclude ipynb (line-wise, robust)
  for($i=0;$i -lt $lines.Count;$i++){
    if($lines[$i] -match '^\s*black\s+--check\b'){
      $ln = $lines[$i]
      if($ln -notmatch '--quiet'){ $ln = $ln -replace '(^\s*black\s+--check\b)','${1} --quiet' }
      if($ln -notmatch '--exclude'){
        # ensure trailing " ." then add exclude
        if($ln -notmatch '\s\.$'){ $ln = $ln.TrimEnd() + ' .' }
        $ln = $ln -replace '\s\.$'," --exclude '\.ipynb$' ."
      }
      $lines[$i] = $ln
    }
  }

  if(-not ($orig -ceq $lines)){
    if(-not $DryRun){ Set-Content -LiteralPath $wf -Value $lines -Encoding UTF8 -NoNewline }
    Changed $wf
    Step "Patched $wf" 'Green'
  } else {
    Step "No changes in $wf" 'DarkGray'
  }
}

# --- 4) Commit/push if we changed anything ---
if($script:__changed){
  Step "Committing & pushing changes"
  if(-not $DryRun){
    git commit -m "ci: normalize LF; ensure workflow_dispatch; quiet Black; add watcher" | Out-Null
    git push | Out-Null
  }
}else{
  Step "Nothing to commit" 'DarkGray'
}

# --- 5) Trigger runs (if requested) ---
if(-not $NoTrigger){
  foreach($wf in $wfFiles){
    try {
      Step "Dispatch $wf on $Branch"
      if(-not $DryRun){ gh workflow run $wf --ref $Branch | Out-Null }
    } catch { Step "Skip dispatch ($wf): $($_.Exception.Message)" 'DarkGray' }
  }
}

# --- 6) Watch (optional) ---
if(-not $NoWatch){
  try {
    Step "Watching CI on $Branch"
    if(-not $DryRun){ pwsh $watchPath -Branch $Branch -Tail $Tail }
  } catch { Step "Watcher error: $($_.Exception.Message)" 'DarkGray' }
}

Write-Host "`n✅ Zero-Touch completed." -ForegroundColor Green
