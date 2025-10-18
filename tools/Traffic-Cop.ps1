param()

$ErrorActionPreference = "Stop"

# Collect candidate files and filter out empties/nonexistent
$files = @( & git ls-files -- "*.ps1" "*.psm1" ".github/workflows/*.yml" ".github/workflows/*.yaml" ) |
  Where-Object { $_ -and (Test-Path -LiteralPath $_) }

$patterns = @(
  "python\s*-\s*<<",   # e.g., python - <<'PY'
  "<<\s*PY\b"          # common heredoc label
)

$bad = @()

foreach ($f in $files) {
  $text = Get-Content -LiteralPath $f -Raw
  foreach ($pat in $patterns) {
    if ($text -match $pat) {
      $bad += [pscustomobject]@{ File = $f; Pattern = $pat }
      break
    }
  }
}

if ($bad.Count) {
  foreach ($b in $bad) {
    Write-Host "::error file=$($b.File)::Bash heredoc detected in PowerShell context. Use a PS here-string piped to python instead."
  }
  Write-Host "Traffic-Cop: Found $($bad.Count) heredoc misuse(s)."
  exit 1
}

Write-Host "Traffic-Cop: OK — no heredoc misuse detected."
