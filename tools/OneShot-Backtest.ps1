param(
  [string]repos:
  - repo: https://github.com/psf/black
    rev: 25.9.0
    hooks:
      - id: black

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.13.2
    hooks:
      - id: ruff
        alias: ruff (legacy alias)

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: end-of-file-fixer
      - id: trailing-whitespace

  - repo: local
    hooks:
      - id: pytest
        name: pytest with coverage
        entry: pytest --maxfail=1 --disable-warnings -q --cov=src --cov-report=term-missing
        language: system
        types: [python]
        pass_filenames: false = "config/production.yaml",
  [string] = "EURUSD,GBPUSD,USDJPY",
  [string] = "1d",
  [string] = "2020-01-01",
  [string] = "2024-12-31",
  [string] = "DEMO",
  [switch],
  [switch]   # set this to also untrack backups & commit helpers
)

function Write-ReqsIfMissing {
  if (-not (Test-Path .\requirements.txt)) {
@'
pandas>=2.0
numpy>=1.26
pyarrow>=15
tqdm>=4.66
PyYAML>=6.0
python-dateutil>=2.8.2
requests>=2.31
matplotlib>=3.8
'@ | Set-Content .\requirements.txt -Encoding UTF8
  }
}

function Ensure-Venv {
   = ".\.venv\Scripts\python.exe"
  if (-not (Test-Path )) {
    Write-Host "Creating venv..."
    py -3.11 -m venv .venv 2>; if (0 -ne 0) { py -m venv .venv }
  }
  &  -m pip install -U pip *>
  Write-ReqsIfMissing
  &  -m pip install -r .\requirements.txt
  return
}

function Ensure-ConfigTools {
  if (-not (Test-Path .\tools\analyze_config.py)) {
@'
import argparse, yaml, sys
from pathlib import Path
ap=argparse.ArgumentParser(); ap.add_argument("--cfg",default="config/production.yaml")
a=ap.parse_args(); p=Path(a.cfg)
cfg={}
if p.exists():
  cfg=yaml.safe_load(p.read_text(encoding="utf-8")) or {}
print("symbols.core present:", bool(cfg.get("symbols",{}).get("core")))
print("symbols.satellite present:", bool(cfg.get("symbols",{}).get("satellite")))
'@ | Set-Content .\tools\analyze_config.py -Encoding UTF8
  }
  if (-not (Test-Path .\tools\fix_config.py)) {
@'
import argparse, yaml, re
from pathlib import Path
ap=argparse.ArgumentParser()
ap.add_argument("--cfg", default="config/production.yaml")
ap.add_argument("--symbols", default="")
ap.add_argument("--satellite", default="")
a=ap.parse_args()
p=Path(a.cfg); p.parent.mkdir(parents=True, exist_ok=True)
cfg={}
if p.exists():
  cfg=yaml.safe_load(p.read_text(encoding="utf-8")) or {}
cfg.setdefault("symbols",{})
S=lambda s:[x.strip().upper() for x in re.split(r"[,\s]+", s) if x.strip()]
core=S(a.symbols) or cfg["symbols"].get("core") or ["EURUSD","GBPUSD","USDJPY"]
sat=S(a.satellite) or cfg["symbols"].get("satellite") or []
cfg["symbols"]["core"]=core; cfg["symbols"]["satellite"]=sat
p.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
print("symbols.core     =", core)
print("symbols.satellite=", sat)
'@ | Set-Content .\tools\fix_config.py -Encoding UTF8
  }
}

function Ensure-Config {
  param(,repos:
  - repo: https://github.com/psf/black
    rev: 25.9.0
    hooks:
      - id: black

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.13.2
    hooks:
      - id: ruff
        alias: ruff (legacy alias)

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: end-of-file-fixer
      - id: trailing-whitespace

  - repo: local
    hooks:
      - id: pytest
        name: pytest with coverage
        entry: pytest --maxfail=1 --disable-warnings -q --cov=src --cov-report=term-missing
        language: system
        types: [python]
        pass_filenames: false,)
  &  .\tools\fix_config.py --cfg repos:
  - repo: https://github.com/psf/black
    rev: 25.9.0
    hooks:
      - id: black

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.13.2
    hooks:
      - id: ruff
        alias: ruff (legacy alias)

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: end-of-file-fixer
      - id: trailing-whitespace

  - repo: local
    hooks:
      - id: pytest
        name: pytest with coverage
        entry: pytest --maxfail=1 --disable-warnings -q --cov=src --cov-report=term-missing
        language: system
        types: [python]
        pass_filenames: false --symbols
}

function Ensure-Data {
  param(,,,,)
   = "data\prices_"
  New-Item -ItemType Directory -Force -Path  | Out-Null
   =  -split "[,\s]+" | Where-Object {  -ne "" }
  foreach ( in ) {
     = Join-Path  ".parquet"
    if (-not (Test-Path )) {
      Write-Host "Downloading   -> "
      &  -m src.data.dukascopy_downloader --symbol  --tf  --start  --end  --out
    } else {
      Write-Host "Found  (skipping)"
    }
  }
}

function Run-Backtest {
  param(,repos:
  - repo: https://github.com/psf/black
    rev: 25.9.0
    hooks:
      - id: black

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.13.2
    hooks:
      - id: ruff
        alias: ruff (legacy alias)

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: end-of-file-fixer
      - id: trailing-whitespace

  - repo: local
    hooks:
      - id: pytest
        name: pytest with coverage
        entry: pytest --maxfail=1 --disable-warnings -q --cov=src --cov-report=term-missing
        language: system
        types: [python]
        pass_filenames: false,,,,)
   = @("-m","src.exec.backtest","--cfg",repos:
  - repo: https://github.com/psf/black
    rev: 25.9.0
    hooks:
      - id: black

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.13.2
    hooks:
      - id: ruff
        alias: ruff (legacy alias)

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: end-of-file-fixer
      - id: trailing-whitespace

  - repo: local
    hooks:
      - id: pytest
        name: pytest with coverage
        entry: pytest --maxfail=1 --disable-warnings -q --cov=src --cov-report=term-missing
        language: system
        types: [python]
        pass_filenames: false,"--out_prefix",)
  if () {  += "--dry_run" }
  if ()  {  += @("--start",) }
  if ()    {  += @("--end",) }
  Write-Host "Running:" ( -join " ")
  &  @args
}

function Git-CleanAndCommit {
  git rm -r --cached "__backup_29-09-25*" "__backup_*" "__backup*" 2>
  if (-not (Test-Path .\.gitignore) -or -not (Select-String -Path .\.gitignore -SimpleMatch ".precommit_cache/" -ErrorAction SilentlyContinue)) {
    Add-Content .\.gitignore "
.precommit_cache/
"
  }
  git add tools\analyze_config.py tools\fix_config.py .gitignore repos:
  - repo: https://github.com/psf/black
    rev: 25.9.0
    hooks:
      - id: black

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.13.2
    hooks:
      - id: ruff
        alias: ruff (legacy alias)

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: end-of-file-fixer
      - id: trailing-whitespace

  - repo: local
    hooks:
      - id: pytest
        name: pytest with coverage
        entry: pytest --maxfail=1 --disable-warnings -q --cov=src --cov-report=term-missing
        language: system
        types: [python]
        pass_filenames: false
  git commit -m "One-shot: config helpers, set symbols, untrack backups, ensure data" 2>
  git push 2>
}

# --- Main flow ---
 = Ensure-Venv
Ensure-ConfigTools
Ensure-Config -venvPy  -Cfg repos:
  - repo: https://github.com/psf/black
    rev: 25.9.0
    hooks:
      - id: black

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.13.2
    hooks:
      - id: ruff
        alias: ruff (legacy alias)

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: end-of-file-fixer
      - id: trailing-whitespace

  - repo: local
    hooks:
      - id: pytest
        name: pytest with coverage
        entry: pytest --maxfail=1 --disable-warnings -q --cov=src --cov-report=term-missing
        language: system
        types: [python]
        pass_filenames: false -Symbols
Ensure-Data -venvPy  -Symbols  -TF  -Start  -End
Run-Backtest -venvPy  -Cfg repos:
  - repo: https://github.com/psf/black
    rev: 25.9.0
    hooks:
      - id: black

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.13.2
    hooks:
      - id: ruff
        alias: ruff (legacy alias)

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: end-of-file-fixer
      - id: trailing-whitespace

  - repo: local
    hooks:
      - id: pytest
        name: pytest with coverage
        entry: pytest --maxfail=1 --disable-warnings -q --cov=src --cov-report=term-missing
        language: system
        types: [python]
        pass_filenames: false -Start  -End  -OutPrefix  -DryRun:
if () { Git-CleanAndCommit }
