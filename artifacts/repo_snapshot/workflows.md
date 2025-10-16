# Workflows

## ci.yml

name: Tests (pytest)on:  push:  pull_request:  workflow_dispatch:defaults:  run:    shell: pwshjobs:  test:    runs-on: ubuntu-latest    steps:      - name: Checkout        uses: actions/checkout@v4      - name: Set up Python        uses: actions/setup-python@v5        with:          python-version: '3.11'      - name: Install deps        run: |          python -m pip install --upgrade pip          pip install -r requirements.txt -c .github/constraints-ci.txt          if ($LASTEXITCODE -ne 0) { Write-Host 'Ignoring constraints install failure'; $global:LASTEXITCODE = 0 }          pip install pytest pytest-cov -c .github/constraints-ci.txt        env:          AF_SKIP_MT5: 1          PYTHONPATH: ${{ github.workspace }}:${{ github.workspace }}/src      - name: Run pytest (smoke)        run: pytest -q --maxfail=1 --disable-warnings tests/ci_smoke_test.py

## drift.yml

name: drift-dashboard

on:
  workflow_run:
    workflows: ["nightly"]
    types: [completed]

jobs:
  drift:
    if: ${{ github.event.workflow_run.conclusion == 'success' }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          python -m pip install pandas matplotlib pyarrow

      - name: Generate drift dashboard
        run: python -m src.infra.drift_dashboard

      - name: Upload drift artifacts
        uses: actions/upload-artifact@v4
        with:
          name: drift-dashboard-${{ github.run_id }}
          path: |
            artifacts/drift_dashboard.html
            artifacts/drift_summary.csv
            artifacts/drift_dashboard.png

## export-features-upload-s3.yml

name: Export Features — Upload to S3 (optional)

on:
  workflow_run:
    workflows: ["Export Features (nightly)"]
    types: [completed]

jobs:
  upload:
    if: >
      ${{ github.event.workflow_run.conclusion == 'success' &&
           secrets.FS_S3_BUCKET != '' &&
           secrets.AWS_REGION != '' &&
           secrets.AWS_ACCESS_KEY_ID != '' &&
           secrets.AWS_SECRET_ACCESS_KEY != '' }}
    runs-on: ubuntu-latest
    steps:
      - name: Download artifacts from previous workflow
        uses: actions/download-artifact@v4
        with:
          name: feature-exports-${{ github.event.workflow_run.id }}
          path: artifacts/exports
        continue-on-error: true

      - name: Ensure fallback if artifact name differs
        run: |
          if [ ! -d "artifacts/exports" ]; then
            mkdir -p artifacts/exports
            echo "No artifacts found; nothing to upload."
          fi

      - name: Install AWS CLI
        run: |
          python -m pip install --upgrade pip
          pip install awscli

      - name: Upload to S3
        env:
          FS_S3_BUCKET: ${{ secrets.FS_S3_BUCKET }}
          AWS_REGION: ${{ secrets.AWS_REGION }}
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        run: |
          if [ -d "artifacts/exports" ]; then
            aws s3 cp "artifacts/exports" "s3://${FS_S3_BUCKET}/exports/${{ github.event.workflow_run.head_branch }}/${{ github.run_id }}/" --recursive --region "${AWS_REGION}"
            echo "Uploaded to s3://${FS_S3_BUCKET}/exports/..."
          else
            echo "Nothing to upload."
          fi

## export-features.yml

name: Export Features (nightly)

on:
  schedule:
    - cron: "15 2 * * *"   # 02:15 UTC nightly
  workflow_dispatch:

permissions:
  contents: read

jobs:
  export:
    runs-on: ubuntu-latest
    defaults:
      run:
        shell: bash
    env:
      PYTHONPATH: "${{ github.workspace }}:${{ github.workspace }}/src"
      FS_DB: "./fs.duckdb"
      FS_PARQUET_DIR: "./artifacts/exports"
      PAIRS: "EURUSD,GBPUSD,USDJPY"
      SPREAD_BPS: "18.0"
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run exporter
        run: |
          python -m src.infra.cli_export

      - name: Upload Parquet artifacts
        uses: actions/upload-artifact@v4
        with:
          name: feature-exports-${{ github.run_id }}
          path: artifacts/exports
          if-no-files-found: warn

## lint.yml

name: Lint (Ruff + Black)on:  push:  pull_request:  workflow_dispatch:defaults:  run:    shell: pwshjobs:  lint:    runs-on: ubuntu-latest    steps:      - name: Checkout        uses: actions/checkout@v4      - name: Set up Python        uses: actions/setup-python@v5        with:          python-version: '3.11'      - name: Install linters        run: |          python -m pip install --upgrade pip          pip install ruff black -c .github/constraints-ci.txt      - name: Ruff        run: ruff check .      - name: Black (check)        run: |          black --check --quiet --exclude '\.ipynb$' .

## nightly.yml

name: Nightly

on:
  schedule:
    - cron: "0 2 * * *"
  workflow_dispatch:

jobs:
  nightly:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt || true
          pip install -q pyarrow fastparquet || true

      - name: Run feature exporter
        run: python -m src.infra.export_features

      - name: Export weights
        run: python -m src.infra.export_weights

      - name: Upload artifacts
        uses: actions/upload-artifact@v4

      - name: Upload regression artifacts
        uses: actions/upload-artifact@v4
        with:
          name: regression-${{ github.run_id }}
          path: |
            artifacts/regression-*.csv
            artifacts/regression-*.json
            artifacts/regression-*.parquet
        with:
          name: feature-exports-${{ github.run_id }}
          path: |
            artifacts/*.parquet

## no-push-guard.yml

name: Check for push or pull_request_target triggers
on:
  pull_request:
  workflow_dispatch:

jobs:
  check-forbidden-triggers:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Fail if forbidden triggers exist
        shell: bash
        run: |
          set -euo pipefail
          shopt -s nullglob
          files=(.github/workflows/*.yml .github/workflows/*.yaml)
          banned=('^\s*push\s*:' '^\s*pull_request_target\s*:')
          bad=0
          for f in "${files[@]}"; do
            for pat in "${banned[@]}"; do
              if grep -P -n "$pat" "$f" >/dev/null 2>&1; then
                echo "::error file=$f::Forbidden trigger matched pattern: $pat"
                bad=1
              fi
            done
          done
          exit $bad

## pr-ci.yml

name: pr-ci
on:
  pull_request:
    branches: [ main ]
jobs:
  pr:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: python -m pip install -U pip && pip install -r requirements.txt -c .github/constraints-ci.txt pytest
      - run: pytest -q

## test.yml

name: Tests (pytest)

on:
  push:
  pull_request:
  workflow_dispatch:

defaults:
  run:
    shell: pwsh

jobs:
  test:
    runs-on: ubuntu-latest
    env:
      AF_SKIP_MT5: '1'
      PYTHONPATH: ${{ github.workspace }}:${{ github.workspace }}/src
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt -c .github/constraints-ci.txt
          if ($LASTEXITCODE -ne 0) { Write-Host 'Ignoring constraints install failure'; $global:LASTEXITCODE = 0 }
          pip install pytest pytest-cov -c .github/constraints-ci.txt

      - name: Run pytest (smoke)
        run: pytest -q --maxfail=1 --disable-warnings tests/ci_smoke_test.py
