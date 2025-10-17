#Requires -Version 7
param(
  [string[]]$Files = @(".github/workflows/lint.yml", ".github/workflows/ci.yml")
)
$ErrorActionPreference = 'Stop'
$changed = 0

foreach($wf in $Files){
  if(-not (Test-Path $wf)) { continue }
  Write-Host "Patching $wf ..." -ForegroundColor Cyan

  $orig = Get-Content -LiteralPath $wf -Encoding UTF8
  $out  = @()

  foreach($l in $orig){
    if($l -match '^\s*black\s+--check\b'){
      # Add --quiet if missing
      $l = $l -replace '(^\s*black\s+--check\b)(?!.*--quiet)', '$1 --quiet'
      # Add --exclude '\.ipynb$' if missing, ensure trailing dot path
      if($l -notmatch '--exclude'){
        # ensure it ends with " ."
        if($l -notmatch '\s\.$'){ $l = $l.TrimEnd() + ' .' }
        $l = $l -replace '\s\.$', " --exclude '`.ipynb$' ."
      }
    }
    $out += $l
  }

  if(-not ($out -ceq $orig)){
    Set-Content -LiteralPath $wf -Value $out -Encoding UTF8 -NoNewline
    git add $wf | Out-Null
    $changed++
    Write-Host "  ✓ Patched Black invocation" -ForegroundColor Green
  } else {
    Write-Host "  • Nothing to change" -ForegroundColor DarkGray
  }
}

if($changed -gt 0){
  git commit -m "ci: quiet Black and exclude .ipynb (PS7 patch)" | Out-Null
  git push | Out-Null
  Write-Host "Done. ($changed file(s) changed & pushed)" -ForegroundColor Green
} else {
  Write-Host "Done. (no changes)" -ForegroundColor Yellow
}
