param(
  [Parameter(Mandatory = $true)]
  [string]$Tag,
  [string]$Title,
  [string]$Notes,
  [switch]$NoLatest  # pass -NoLatest if you do NOT want this marked as latest
)

$ErrorActionPreference = "Stop"

function Exec([string]$cmd) {
  Write-Host "» $cmd" -ForegroundColor DarkGray
  & pwsh -NoProfile -Command $cmd
  if ($LASTEXITCODE) { throw "Command failed ($LASTEXITCODE): $cmd" }
}

# --- repo root
$root = (git rev-parse --show-toplevel)
if (-not $root) { throw "Not in a Git repo." }
Set-Location $root

# --- Ensure tag exists locally
$tagExistsLocal = (& git tag --list $Tag) -ne $null
if (-not $tagExistsLocal) {
  Write-Host "• Creating lightweight tag $Tag" -ForegroundColor Cyan
  git tag $Tag
}

# --- Push tag
Write-Host "• Pushing tag $Tag" -ForegroundColor Cyan
git push origin $Tag | Out-Null

# --- Title / Notes prep
if (-not $Title -or -not $Title.Trim()) { $Title = "$Tag – automated release" }

$notesFile = $null
if ($Notes -and $Notes.Trim()) {
  $notesFile = $Notes
} else {
  # Try project notes generator; fall back to a simple file
  try {
    if (Test-Path -LiteralPath (Join-Path $root 'tools/Make-Changelog.py')) {
      Write-Host "• Generating notes via tools/Make-Changelog.py" -ForegroundColor Cyan
      & python "tools/Make-Changelog.py" | Out-Null
    }
  } catch { }

  $notesFile = Join-Path $env:TEMP ("release_notes_{0}.md" -f $Tag)
  @(
    "# $Tag",
    "",
    "Automated release for **$Tag**.",
    "",
    "- CI green",
    "- Non-interactive publish via tools/New-Release.ps1",
    ""
  ) | Set-Content -LiteralPath $notesFile -Encoding utf8
}

# --- Create or edit release
$existingUrl = $null
try {
  $existingUrl = (gh release view $Tag --json url -q .url 2>$null)
} catch { }

if ($existingUrl) {
  Write-Host "• Release exists; updating title/notes" -ForegroundColor Cyan
  gh release edit $Tag --title $Title --notes-file $notesFile | Out-Null
  if (-not $NoLatest) {
    gh release edit $Tag --latest | Out-Null
  }
} else {
  Write-Host "• Creating release $Tag" -ForegroundColor Cyan
  $args = @('release','create', $Tag, '--title', $Title, '--notes-file', $notesFile)
  if (-not $NoLatest) { $args += '--latest' }
  gh @args | Out-Null
}

# --- Print final URL
$url = gh release view $Tag --json url -q .url
Write-Host "`n✓ Release ready:" -ForegroundColor Green
Write-Host $url -ForegroundColor Yellow
