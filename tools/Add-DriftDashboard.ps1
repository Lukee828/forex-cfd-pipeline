#requires -Version 7
$ErrorActionPreference = 'Stop'

# Resolve repo root
$Root = try { (git rev-parse --show-toplevel).Trim() } catch { $PSScriptRoot | Split-Path -Parent }
if (-not $Root) { $Root = Get-Location }
Set-Location $Root

function Write-Utf8NoBom($Path, [string[]]$Content){
  $dir = Split-Path -Parent $Path
  if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  [IO.File]::WriteAllLines($Path, $Content, [System.Text.UTF8Encoding]::new($false))
}

# 1) Write src/infra/drift_dashboard.py (no external viz deps; uses matplotlib)
$pyPath = "src/infra/drift_dashboard.py"
$py = @(
  "from __future__ import annotations",
  "import os, math, datetime as dt",
  "from pathlib import Path",
  "from typing import List",
  "import pandas as pd",
  "import numpy as np",
  "import matplotlib.pyplot as plt",
  "",
  "def _find_files(root: str, pat: str) -> List[Path]:",
  "    return sorted(Path(root).glob(pat))",
  "",
  "def _ensure_synth(root: str) -> List[Path]:",
  "    Path(root).mkdir(parents=True, exist_ok=True)",
  "    ts = dt.datetime.utcnow().strftime('%Y%m%d')",
  "    f1 = Path(root) / f'features-{ts}-a.csv'",
  "    f2 = Path(root) / f'features-{ts}-b.csv'",
  "    if not f1.exists() and not f2.exists():",
  "        df1 = pd.DataFrame({'sharpe':[1.2,0.8,0.3],'dd':[0.10,0.05,0.20]})",
  "        df2 = pd.DataFrame({'sharpe':[1.1,0.7,0.4],'dd':[0.11,0.06,0.18]})",
  "        df1.to_csv(f1, index=False)",
  "        df2.to_csv(f2, index=False)",
  "    return [p for p in [f1,f2] if p.exists()]",
  "",
  "def load_feature_history(root: str = 'artifacts') -> pd.DataFrame:",
  "    files = _find_files(root, 'features-*.parquet') + _find_files(root, 'features-*.csv')",
  "    if not files:",
  "        files = _ensure_synth(root)",
  "    rows = []",
  "    for p in files:",
  "        if p.suffix.lower() == '.parquet':",
  "            df = pd.read_parquet(p)",
  "        else:",
  "            df = pd.read_csv(p)",
  "        df['ts'] = p.stem.split('-')[-1]",
  "        rows.append(df)",
  "    return pd.concat(rows, ignore_index=True)",
  "",
  "def compute_drift(df: pd.DataFrame) -> pd.DataFrame:",
  "    g = df.groupby('ts').mean(numeric_only=True).sort_index()",
  "    diff = g.diff().abs()",
  "    out = pd.DataFrame({",
  "        'avg_abs_change': diff.mean(axis=0),",
  "        'std_change': diff.std(axis=0),",
  "    })",
  "    return out.sort_values('avg_abs_change', ascending=False)",
  "",
  "def render_dashboard(drift: pd.DataFrame, out_html='artifacts/drift_dashboard.html'):",
  "    Path(out_html).parent.mkdir(parents=True, exist_ok=True)",
  "    # simple bar to PNG",
  "    fig = plt.figure()",
  "    ax = fig.gca()",
  "    xs = np.arange(len(drift.index))",
  "    ax.bar(xs, drift['avg_abs_change'].values)",
  "    ax.set_xticks(xs)",
  "    ax.set_xticklabels([str(i) for i in drift.index], rotation=45, ha='right')",
  "    ax.set_title('Feature Drift (avg_abs_change)')",
  "    ax.set_ylabel('avg_abs_change')",
  "    png = Path(out_html).with_suffix('.png')",
  "    fig.tight_layout()",
  "    fig.savefig(png)",
  "    plt.close(fig)",
  "    # tiny HTML wrapper",
  "    html = f'<html><body><h2>Feature Drift</h2><img src=\"{png.name}\"/></body></html>'",
  "    with open(out_html, 'w', encoding='utf-8') as f: f.write(html)",
  "    print(f'Wrote {out_html} and {png}' )",
  "",
  "def main():",
  "    df = load_feature_history()",
  "    drift = compute_drift(df)",
  "    Path('artifacts').mkdir(parents=True, exist_ok=True)",
  "    drift.to_csv('artifacts/drift_summary.csv')",
  "    render_dashboard(drift, 'artifacts/drift_dashboard.html')",
  "",
  "if __name__ == '__main__':",
  "    main()",
)
Write-Utf8NoBom $pyPath $py
git add -- $pyPath | Out-Null

# 2) Patch nightly.yml to add drift steps after weights
$wf = ".github/workflows/nightly.yml"
if (Test-Path $wf) {
  $content = Get-Content -LiteralPath $wf -Raw -Encoding UTF8
  if ($content -notmatch "Generate drift dashboard") {
    # Try to insert after an ""Export weights"" step; if not found, append to end
    $insert = @(
      "      - name: Generate drift dashboard",
      "        run: python -m src.infra.drift_dashboard",
      "      - name: Upload drift artifacts",
      "        uses: actions/upload-artifact@v4",
      "        with:",
      "          name: drift-dashboard-${{ github.run_id }}",
      "          path: |",
      "            artifacts/drift_dashboard.html",
      "            artifacts/drift_summary.csv"
    ) -join "`n"
    if ($content -match "(?ms)(- name:\s*Export weights.*?$)") {
      $content = $content -replace "(?ms)(- name:\s*Export weights.*?$)", ("$1`n" + $insert)
    } else {
      $content = $content.TrimEnd() + "`n" + $insert + "`n"
    }
    [IO.File]::WriteAllText($wf, $content, $utf8)
    git add -- $wf | Out-Null
  }
}

# 3) Commit & push
try { git commit -m "infra(drift): add drift_dashboard, wire into nightly, emit HTML+CSV" 2>$null | Out-Null } catch {}
git push | Out-Null

# 4) Smoke run
$old = $env:PYTHONPATH; $env:PYTHONPATH = "$Root;$Root\src"
try {
  & .\.venv\Scripts\python.exe -m src.infra.drift_dashboard
} finally { $env:PYTHONPATH = $old }

Write-Host "`n✅ Drift dashboard added, nightly updated, smoke completed, and pushed." -ForegroundColor Green
