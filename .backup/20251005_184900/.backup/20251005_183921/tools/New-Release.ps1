param(
    [ValidateSet('major','minor','patch')]
    [string]$Bump = 'patch',
    [string]$RunsDir = 'runs',
    [int]$MaxGrids = 12,
    [switch]$Plot,
    [int]$Top = 10,
    [switch]$Push,
    [switch]$GithubRelease
)
function New-ReleaseNotes {
  param(
    [string]$VersionTag,
    [string]$RunsDir = 'runs',
    [int]$Top = 10
  )

  $lines = @("# Release $VersionTag", "")

  $cons = Join-Path $RunsDir 'best_params_consensus.csv'
  if (Test-Path $cons) {
    try {
      $rows = Import-Csv $cons | Select-Object -First $Top `
        @{n='fast';e={[int]$_.fast}},
        @{n='slow';e={[int]$_.slow}},
        @{n='Sharpeμ';e={[double]([string]$_.sharpe_mean -replace ",",".")}},
        @{n='Sharpeσ';e={[double]([string]$_.sharpe_std  -replace ",",".")}},
        @{n='Calmarμ';e={[double]([string]$_.calmar_mean -replace ",",".")}},
        @{n='obs';e={[int]$_.obs}}

      $lines += @(
        "## Top consensus (robustness)", "",
        "| fast | slow | Sharpeμ | Sharpeσ | Calmarμ | obs |",
        "|---:|---:|---:|---:|---:|---:|"
      )
      foreach ($r in $rows) {
        $lines += ("| {0} | {1} | {2:N2} | {3:N2} | {4:N2} | {5} |" -f `
          $r.fast,$r.slow,$r.'Sharpeμ',$r.'Sharpeσ',$r.'Calmarμ',$r.obs)
      }
      $lines += ""
    } catch {
      $lines += "_(couldn't parse consensus CSV)_"
    }
  } else {
    $lines += "_(consensus CSV not found)_"
  }

  return ($lines -join "`n")
}

$ErrorActionPreference = 'Stop'
$py = ".\.venv\Scripts\python.exe"

function Get-LastTag {
  $t = (git describe --tags --abbrev=0 2>$null)
  if (-not $t) { return "v0.0.0" }
  return $t.Trim()
}

function Bump-SemVer([string]$tag, [string]$kind) {
  if ($tag -match 'v?(\d+)\.(\d+)\.(\d+)') {
    $maj = [int]$Matches[1]; $min = [int]$Matches[2]; $pat = [int]$Matches[3]
  } else { $maj=0;$min=0;$pat=0 }
  switch ($kind) {
    "major" { $maj++; $min=0; $pat=0 }
    "minor" { $min++; $pat=0 }
    default { $pat++ }
  }
  return "v{0}.{1}.{2}" -f $maj,$min,$pat
}

# 1) Recompute comparisons & artifacts
$compare = "tools/Compare-Grids.ps1"
if (-not (Test-Path $compare)) { throw "Missing $compare" }
$compareArgs = @('-RunsDir', $RunsDir, '-MaxGrids', $MaxGrids, '-Top', $Top)
if ($Plot) { $compareArgs += '-Plot' }
pwsh -File $compare @compareArgs

# Force UTF-8 for Python stdout + console
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONIOENCODING = 'utf-8'

# 2) Build changelog markdown (stdout)
$md = # Generate changelog with UTF-8 explicitly enabled
$python = $venvPy
if (-not $python) { $python = $py }
if (-not $python) { $python = "python" }

& $python -X utf8 tools/Make-Changelog.py | Set-Content -Encoding UTF8 CHANGELOG.md
if ($LASTEXITCODE -ne 0) { throw "Make-Changelog failed" }
if ($LASTEXITCODE -ne 0) { throw "Make-Changelog failed" }

# 3) Compute next tag
$last = Get-LastTag
$next = Bump-SemVer $last $Bump
Write-Host "Last tag: $last  -> Next: $next" -ForegroundColor Cyan

# 4) Write the release notes to a temp file
$notesPath = Join-Path $env:TEMP ("release_notes_{0}.md" -f $next)
$md | Set-Content -Encoding UTF8 $notesPath

# 5) Create annotated tag
git tag -a $newTag -m $tagMessage
Write-Host "Created tag $next" -ForegroundColor Green

if ($Push) {
  git push origin $next
  Write-Host "Pushed tag $next" -ForegroundColor Green
}

# 6) Optionally create a GitHub release with artifacts via gh CLI
if ($GithubRelease) {
  # collect artifacts
  $latestGrid = (Get-ChildItem $RunsDir -Directory -Filter "ma_grid_*" | Sort-Object LastWriteTime -Desc | Select-Object -First 1)
  $artifacts = @()
  $artifacts += (Join-Path $RunsDir "all_grids_combined.csv")
  $artifacts += (Join-Path $RunsDir "grid_stability_by_bps.csv")
  $artifacts += (Join-Path $RunsDir "best_params_consensus.csv")
  if ($latestGrid) {
    $artifacts += (Join-Path $latestGrid.FullName "heatmap_sharpe.csv")
    $artifacts += (Join-Path $latestGrid.FullName "heatmap_calmar.csv")
    $artifacts += (Join-Path $latestGrid.FullName "heatmap_sharpe.png")
    $artifacts += (Join-Path $latestGrid.FullName "heatmap_calmar.png")
  }
  $artifacts = $artifacts | Where-Object { Test-Path $_ }

  $args = @('release','create', $next, '--title', $next, '--notes-file', $notesPath)
  if ($artifacts.Count -gt 0) { $args += $artifacts }

  try {
    gh @args
    Write-Host "GitHub release $next created." -ForegroundColor Green
  } catch {
    Write-Warning "gh CLI not available or release failed: $($_.Exception.Message)"
  }
}

Write-Host "`nDone. Tag: $next  Notes: $notesPath" -ForegroundColor Yellow








gh release create $newTag --title $newTag --notes-file $notesPath --latest
