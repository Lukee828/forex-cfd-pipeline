param(
  [string]$Parquet = "data",
  [string]$Symbol  = "EURUSD",
  [int]$Fast = 10,
  [int]$Slow = 50
)
$py   = ".\.venv\Scripts\python.exe"
$code = @"
import sys, os, pandas as pd
parquet, sym, fast, slow = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
p = os.path.join(parquet, f"{sym}.parquet")
df = pd.read_parquet(p)
cl = df["Close"].rename("Close").sort_index()
print(f"Loaded {sym} closes: len={len(cl)}  first={cl.index[0]}  last={cl.index[-1]}")
if len(cl) < slow:
    print(f"Not enough history: len={len(cl)} < slow={slow}")
    sys.exit(0)
fma = cl.rolling(window=fast).mean().iloc[-1]
sma = cl.rolling(window=slow).mean().iloc[-1]
print(f"fast={fast} slow={slow}  fastMA(last)={fma:.6f}  slowMA(last)={sma:.6f}")
"@
& $py -c $code $Parquet $Symbol $Fast $Slow
