# Alpha Factory — AI Governance Bootstrap (v2)

Created: 2025-10-18T12:03:14

## Quick start
1. Python 3.11 + PowerShell 7
2. Install deps:
   ```ps1
   python -m venv .venv311
   .\.venv311\Scripts\Activate.ps1
   pip install black ruff pytest jsonschema pyyaml fastapi uvicorn
   Install-Module PowerShell.Yaml -Scope CurrentUser -Force
   ```
3. Self-test:
   ```ps1
   pwsh tools/Bootstrap-SelfTest.ps1
   ```
4. Run agent (optional):
   ```ps1
   .\.venv311\Scripts\python.exe -m uvicorn ai_lab.serve_agent:app --host 127.0.0.1 --port 8000
   ```
