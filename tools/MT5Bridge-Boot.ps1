[CmdletBinding()] param([string]$Config = "configs/bridge_mt5.yaml")
$ErrorActionPreference = "Stop"
$root = (Get-Location).Path
$py   = Join-Path $root ".venv311\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $py)) { throw "Python venv not found: $py" }
# kill old job if any
Get-Job -Name MT5Bridge -ErrorAction SilentlyContinue | Remove-Job -Force -ErrorAction SilentlyContinue | Out-Null
# start new
$job = Start-Job -Name MT5Bridge -ScriptBlock { param($r,$p,$c) Set-Location $r; & $p -m alpha_factory.bridge.bridge_mt5 --config $c --serve } -ArgumentList $root,$py,$Config
Write-Host "Bridge server job started: $($job.Id)"
# wait for port 5005
$ok=$false; for($i=0;$i -lt 40;$i++){ if(Get-NetTCPConnection -LocalPort 5005 -State Listen -ErrorAction SilentlyContinue){$ok=$true;break}; Start-Sleep -Milliseconds 250 }
if($ok){ Write-Host "Bridge is listening on 127.0.0.1:5005" } else { Write-Warning "Bridge not listening yet" }
# quick ping
& $py -m alpha_factory.bridge.bridge_mt5 --config $Config --ping