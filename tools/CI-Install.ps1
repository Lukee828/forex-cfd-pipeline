$ErrorActionPreference = "Stop"
if (-not (Test-Path .\.venv311\Scripts\Activate.ps1)) { python -m venv .venv311 }
.\.venv311\Scripts\Activate.ps1
python -m pip install --upgrade pip
if (Test-Path .github/constraints-ci.txt) { pip install -r requirements.txt -c .github/constraints-ci.txt } else { pip install -r requirements.txt }
if (Test-Path requirements-dev.txt) { pip install -r requirements-dev.txt }
pip install pytest pytest-cov jsonschema
