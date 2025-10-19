param()
[CmdletBinding()]
param()

[CmdletBinding()]
param(
  [ValidateSet('scaffold','deploy','ping','start','all')][string]$Task = 'all',
  [string]$MT5DataDir = '',
  [string]$Host = '127.0.0.1',
  [int]$Port = 5005,
  [string]$VenvPython = '.\.venv311\Scripts\python.exe',
  [string]$Module = 'alpha_factory.bridge.bridge_mt5',
  [string]$Config = 'configs/bridge_mt5.yaml'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Log([string]$msg,[string]$lvl='INFO'){
  $ts = (Get-Date).ToString('s'); Write-Host "[$ts][$lvl] $msg"
}

function Do-Scaffold {
  $root = $PWD
  $mk = @(
    'configs','logs','mt5\EA','alpha_factory\bridge'
  ) | ForEach-Object { Join-Path $root $_ }
  foreach($d in $mk){ if(!(Test-Path $d)){ New-Item -ItemType Directory -Force -Path $d | Out-Null; Write-Log "Created $d" } }

  $cfg = Join-Path $root 'configs\bridge_mt5.yaml'
  if(!(Test-Path $cfg)){
@"
MT5:
  host: 127.0.0.1
  port: 5005
  heartbeat_sec: 5
  reconnect_sec: 10
  allowed_symbols: [XAUUSD, US30.cash, GER40.cash]
  max_concurrent_orders: 2
Risk:
  max_drawdown_pct: 7
  spread_guard: 0.6
  cost_window_hourly: [7, 22]
Logs:
  path: logs/bridge
  rotate_mb: 50
"@ | Set-Content -Encoding UTF8 $cfg
    Write-Log "Wrote $cfg"
  } else { Write-Log "Config exists: $cfg" 'WARN' }

  $py = Join-Path $root 'alpha_factory\bridge\bridge_mt5.py'
  if(!(Test-Path $py)){
@"# Placeholder for Python bridge.
# Run: .\.venv311\Scripts\python.exe -m alpha_factory.bridge.bridge_mt5 --config configs/bridge_mt5.yaml
if __name__ == '__main__':
    import time, sys
    print('bridge_mt5 placeholder running (stdout). Args:', sys.argv); sys.stdout.flush()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
"@ | Set-Content -Encoding UTF8 $py; Write-Log "Wrote $py"
  }

  $ea = Join-Path $root 'mt5\EA\AF_BridgeEA.mq5'
  if(!(Test-Path $ea)){
@"// Placeholder for AF_BridgeEA.mq5 (compile in MetaEditor)
#property strict
"@ | Set-Content -Encoding UTF8 $ea; Write-Log "Wrote $ea"
  }

  try { git add --all 2>$null; Write-Log 'Staged with git' } catch { Write-Log 'git staging skipped' 'WARN' }
  Write-Log 'Scaffold complete.'
}

function Do-Deploy([string]$MT5DataDir){
  if([string]::IsNullOrWhiteSpace($MT5DataDir)){ throw '-MT5DataDir is required' }
  $src = Join-Path $PWD 'mt5\EA\AF_BridgeEA.mq5'
  if(!(Test-Path $src)){ throw "EA not found: $src (run scaffold first)" }
  $dst = Join-Path (Resolve-Path $MT5DataDir) 'MQL5\Experts\AlphaFactory'
  if(!(Test-Path $dst)){ New-Item -ItemType Directory -Force -Path $dst | Out-Null }
  $target = Join-Path $dst (Split-Path $src -Leaf)
  Copy-Item -Force $src $target
  Write-Log "EA deployed: $target"
}

function Do-Ping([string]$Host,[int]$Port,[int]$TimeoutSec=5){
  $client = [System.Net.Sockets.TcpClient]::new()
  if(-not $client.ConnectAsync($Host,$Port).Wait($TimeoutSec*1000)){ throw "Connection timeout to $Host:$Port" }
  $s = $client.GetStream(); $s.ReadTimeout=$TimeoutSec*1000; $s.WriteTimeout=$TimeoutSec*1000
  $obj = [ordered]@{ type='HEARTBEAT'; ts=(Get-Date).ToUniversalTime().ToString('o'); payload='mt5-ping' }
  $json = ($obj | ConvertTo-Json -Compress)
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($json + "`n")
  $s.Write($bytes,0,$bytes.Length); $s.Flush()
  Write-Log ("Sent: {0}" -f $json)
  $buf = New-Object byte[] 4096; $sb = [System.Text.StringBuilder]::new()
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  while($sw.Elapsed.TotalSeconds -lt $TimeoutSec){
    if($s.DataAvailable){
      $r = $s.Read($buf,0,$buf.Length); if($r -le 0){ break }
      $sb.Append([System.Text.Encoding]::UTF8.GetString($buf,0,$r)) | Out-Null
      if($sb.ToString().Contains("`n")){ break }
    } else { Start-Sleep -Milliseconds 50 }
  }
  $resp = $sb.ToString().Trim()
  if([string]::IsNullOrWhiteSpace($resp)){ Write-Log 'No response (server may be heartbeat-only)' 'WARN' } else { Write-Log ("Recv: {0}" -f $resp) }
  $s.Close(); $client.Close()
}

function Do-Start([string]$VenvPython,[string]$Module,[string]$Config,[switch]$Detach){
  if(!(Test-Path $VenvPython)){ throw "Python not found at $VenvPython" }
  if(!(Test-Path $Config)){ throw "Config not found: $Config (run scaffold)" }
  $logDir = Join-Path $PWD 'logs\bridge'; if(!(Test-Path $logDir)){ New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
  $stamp = (Get-Date).ToString('yyyyMMdd_HHmmss'); $log = Join-Path $logDir "bridge_$stamp.log"
  $argLine = "-m $Module --config `"$Config`""
  if($Detach){
    $p = Start-Process -FilePath (Resolve-Path $VenvPython) -ArgumentList $argLine -RedirectStandardOutput $log -RedirectStandardError $log -PassThru -WindowStyle Hidden
    Write-Log ("Bridge started (PID {0}). Logs: {1}" -f $p.Id,$log)
  } else {
    Write-Log ("Launching: {0} {1}" -f $VenvPython,$argLine)
    & $VenvPython -m $Module --config $Config 2>&1 | Tee-Object -FilePath $log
  }
}

switch($Task){
  'scaffold' { Do-Scaffold }
  'deploy'   { Do-Deploy -MT5DataDir $MT5DataDir }
  'ping'     { Do-Ping -Host $Host -Port $Port }
  'start'    { Do-Start -VenvPython $VenvPython -Module $Module -Config $Config }
  'all'      {
     Do-Scaffold
     if(-not [string]::IsNullOrWhiteSpace($MT5DataDir)){ Do-Deploy -MT5DataDir $MT5DataDir }
     Do-Start -VenvPython $VenvPython -Module $Module -Config $Config -Detach
     Start-Sleep -Seconds 2
     Do-Ping -Host $Host -Port $Port
  }
}
Write-Log "Rollout task '$Task' complete."
