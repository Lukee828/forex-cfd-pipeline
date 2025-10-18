param()
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
function Info($m){ Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "[OK]   $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[WARN] $m" -ForegroundColor Yellow }

$tag = "v0.2.4-registry-analytics"
$notesPath = "release_notes_$($tag).md"

if (git rev-parse --verify $tag 2>$null) {
  Warn "Tag $tag already exists."
} else {
  git add -A
  git commit -m "feat(registry): analytics + provenance extensions (v0.2.4 scaffold)" --allow-empty | Out-Null
  git tag $tag
  Ok "Created tag $tag"
}

$notes = @"
### $tag — Registry Analytics & Provenance
- Added analytics: get_summary, compare, rank (via alpha_registry_ext).
- Added provenance: register_run, get_lineage with runs_metadata table.
- Dashboard: drift_dashboard.plot_alpha_performance() → PNG.
- Overlay: src/alpha_factory/config_registry.yaml.
- Docs & tests: example_registry_usage.py, tests/test_registry.py.
"@
[IO.File]::WriteAllText($notesPath, ($notes -replace "`r?`n","`n"), (New-Object System.Text.UTF8Encoding($false)))
Ok "Wrote $notesPath"

