$ErrorActionPreference = "Stop"
& pwsh -NoProfile -ExecutionPolicy Bypass -File "tools/Verify-Manifest.ps1" -Update
exit 0  # do not fail pre-commit; we only update here
