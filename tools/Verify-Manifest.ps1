param()

# Fail-fast & stricter semantics for PS7 scripts
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0
# tools/Verify-Manifest.ps1
$ErrorActionPreference = 'Stop'

Write-Host "[INFO] Running manifest verification..." -ForegroundColor Cyan

# 1) Build live manifest of all tracked .py and .ps1 files
$live = Get-ChildItem -Recurse src, tools |
    Where-Object { $_.Extension -in '.py', '.ps1' } |
    ForEach-Object {
        "{0}  {1}" -f ((Get-FileHash $_.FullName -Algorithm SHA256).Hash), $_.FullName
    }

# 2) Load reference manifest
if (!(Test-Path 'manifest-sha256.txt')) {
    Write-Host "[FAIL] manifest-sha256.txt not found at repo root." -ForegroundColor Red
    exit 2
}
$ref = Get-Content 'manifest-sha256.txt'

# 3) Compare
$diff = Compare-Object -ReferenceObject $ref -DifferenceObject $live
if ($diff) {
    Write-Host "[WARN] Manifest drift detected:" -ForegroundColor Yellow
    $diff | Format-Table
    exit 1
}

Write-Host "[OK]  Integrity OK — manifest matches." -ForegroundColor Green
