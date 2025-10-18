param(
  [string]$Python      = "python",
  [string]$Venv        = ".venv311",
  [string]$Req         = "requirements.txt",
  [string]$DevReq      = "requirements-dev.txt",
  [string]$Constraints = ".github/constraints-ci.txt"
)

$ErrorActionPreference = "Stop"

# Create venv if missing and activate
if (-not (Test-Path (Join-Path $Venv "Scripts/Activate.ps1"))) {
  & $Python -m venv $Venv
}
. (Join-Path $Venv "Scripts/Activate.ps1")

# Base tools
python -m pip install --upgrade pip

# Install main requirements (use constraints if present)
if (Test-Path $Req) {
  if (Test-Path $Constraints) {
    pip install -r $Req -c $Constraints
  } else {
    pip install -r $Req
  }
}

# Dev requirements if provided
if (Test-Path $DevReq) {
  pip install -r $DevReq
}

# Test deps commonly used by the suite
pip install pytest pytest-cov jsonschema
