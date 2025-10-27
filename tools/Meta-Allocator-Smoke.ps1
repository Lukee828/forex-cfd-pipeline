param(
  [string]$Repo = "C:\Users\speed\Desktop\forex-standalone"
)
$ErrorActionPreference="Stop"
Set-Location $Repo
$env:PYTHONPATH = "$PWD\src"
.\.venv311\Scripts\python.exe - <<'PY'
from alpha_factory.meta_allocator import MetaAllocator, AllocatorConfig
m = MetaAllocator(AllocatorConfig())
metrics = {"A":{"sharpe":1.0,"dd":0.05},"B":{"sharpe":0.8,"dd":0.04}}
w = m.allocate(metrics, prev_weights={"A":0.5,"B":0.5}, corr={("A","B"):0.7})
print("weights", w, "sum", sum(w.values()))
PY
