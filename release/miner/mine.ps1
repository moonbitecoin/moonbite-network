# MoonBite solo miner - Windows (PowerShell).
#
# Mining is solo and pool-free: this runs a full MoonBite node on your PC and
# mines directly to your own wallet. No pool, no middleman, no account. Every
# block you find pays you, and only you.
#
#   .\mine.ps1            start the node and mine
#   .\mine.ps1 address    just print your mining address
#   .\mine.ps1 stop       stop the node
#
# Your wallet lives in the data directory below. BACK IT UP - lose it and you
# lose the coins.
param([string]$cmd = "mine")
$ErrorActionPreference = "Stop"

$here    = Split-Path -Parent $MyInvocation.MyCommand.Path
$daemon  = Join-Path $here "moonbited.exe"
$clibin  = Join-Path $here "moonbite-cli.exe"
if (-not (Test-Path $daemon)) { Write-Error "moonbited.exe not found next to this script."; exit 1 }

$datadir = if ($env:MOONBITE_DATADIR) { $env:MOONBITE_DATADIR } else { Join-Path $env:USERPROFILE ".moonbite" }
$conf    = Join-Path $datadir "moonbite.conf"
$wallet  = "wallet"

# NOTE: do not name this "Cli" - PowerShell ships a built-in alias cli -> Clear-Item
# and aliases take precedence over functions, so "Cli getblockcount" would run
# Clear-Item and throw "Cannot find path ...\getblockcount".
function Invoke-Cli { & $clibin "-datadir=$datadir" "-conf=$conf" @args }

function Write-Conf {
  New-Item -ItemType Directory -Force -Path $datadir | Out-Null
  $pw = $null
  if (Test-Path $conf) { $pw = (Select-String -Path $conf -Pattern '^rpcpassword=(.*)$').Matches.Groups[1].Value }
  if (-not $pw) { $pw = -join ((1..48) | ForEach-Object { '{0:x}' -f (Get-Random -Max 16) }) }
  @"
server=1
listen=1
dbcache=512
rpcuser=moonminer
rpcpassword=$pw
addnode=67.205.154.64:9444
"@ | Set-Content -Encoding ascii $conf
}

function Wait-Rpc { for ($i=0; $i -lt 90; $i++) { try { Invoke-Cli getblockcount | Out-Null; return } catch { Start-Sleep 2 } } throw "node did not start" }

function Start-Node {
  try { Invoke-Cli getblockcount | Out-Null; return } catch {}
  Write-Conf
  # Windows Core has no fork(), so -daemon is unsupported. Launch the node as a
  # detached, hidden background process instead; Wait-Rpc blocks until it's up.
  # One RandomX thread per PHYSICAL core: each VM needs 2 MB of L3, so running a
  # thread per hyper-thread thrashes the cache and is measurably slower.
  $cores = (Get-CimInstance Win32_Processor | Measure-Object -Property NumberOfCores -Sum).Sum
  if (-not $cores -or $cores -lt 1) { $cores = 1 }
  Start-Process -FilePath $daemon -ArgumentList "-datadir=$datadir","-conf=$conf","-miningthreads=$cores" -WindowStyle Hidden | Out-Null
  Wait-Rpc
}

function Ensure-Wallet {
  # Retry: right after startup the wallet subsystem may not be ready yet, and
  # createwallet/loadwallet can transiently fail. Keep trying until "wallet" is
  # in listwallets. Pass load_on_startup=true so it survives a node restart.
  for ($i=0; $i -lt 30; $i++) {
    try { if ((Invoke-Cli listwallets) -match "`"$wallet`"") { return } } catch {}
    try { Invoke-Cli createwallet $wallet false false "" false false true | Out-Null; Start-Sleep 1; continue } catch {}
    try { Invoke-Cli loadwallet $wallet true | Out-Null; Start-Sleep 1; continue } catch {}
    Start-Sleep 2
  }
  throw "could not create or load wallet '$wallet' (see $datadir\debug.log)"
}

function Mining-Address {
  $f = Join-Path $datadir "mining-address.txt"
  if (Test-Path $f) { $cached = (Get-Content $f -Raw).Trim(); if ($cached) { return $cached } }
  for ($i=0; $i -lt 20; $i++) {
    try { $a = Invoke-Cli "-rpcwallet=$wallet" getnewaddress "mining"; if ($a) { Set-Content -Encoding ascii $f $a; return $a } } catch { Start-Sleep 2 }
  }
  throw "could not get a mining address from wallet '$wallet'"
}

switch ($cmd) {
  "address" { Start-Node; Ensure-Wallet; Write-Host "Your mining address: $(Mining-Address)" }
  "stop"    {
    # Kill an in-flight generatetoaddress first, else the busy daemon makes
    # `cli stop` look like it hangs.
    Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*moonbite-cli*generatetoaddress*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    try { Invoke-Cli stop } catch {}
    for ($i=0; $i -lt 20; $i++) { if (-not (Get-Process moonbited -ErrorAction SilentlyContinue)) { break }; Start-Sleep 2 }
    Get-Process moonbited -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "stopped."
  }
  "mine"    {
    Start-Node; Ensure-Wallet
    $addr = Mining-Address
    Write-Host "======================================================================"
    Write-Host " MoonBite solo miner"
    Write-Host " Mining to: $addr"
    Write-Host " Wallet:    $datadir\$wallet   (back this up)"
    Write-Host " Ctrl-C to stop. Coins are spendable 100 blocks after being mined."
    Write-Host "======================================================================"
    # Wait until the node is caught up to the network before mining; mining on a
    # stale tip only makes blocks the network rejects (bad-cb-height).
    Write-Host " Syncing with the network before mining..."
    while ($true) {
      try {
        $info = Invoke-Cli getblockchaininfo | Out-String | ConvertFrom-Json
        if (-not $info.initialblockdownload -and $info.blocks -ge $info.headers) { break }
        Write-Host "   ...$($info.blocks) / $($info.headers) blocks"
      } catch {}
      Start-Sleep 3
    }
    Write-Host " Synced at height $(Invoke-Cli getblockcount). Mining now."
    $found = 0
    while ($true) {
      try {
        $tries = if ($env:MAXTRIES) { $env:MAXTRIES } else { "100000" }
        # generatetoaddress returns the hashes it actually mined; trust that,
        # not a height delta (height also moves when a peer's block arrives).
        $out = ""
        try { $out = (Invoke-Cli "-rpcwallet=$wallet" generatetoaddress 1 $addr $tries | Out-String) } catch {}
        if ($out -match '[0-9a-f]{64}') { $found++; Write-Host "  BLOCK FOUND!  height $(Invoke-Cli getblockcount)   (found $found this session)   peers $(Invoke-Cli getconnectioncount)" }
      } catch {
        # node busy/restarting: log and keep going rather than exiting the miner
        Write-Host "  (rpc hiccup: $($_.Exception.Message.Split([char]10)[0])) retrying..."
        Start-Sleep 5
      }
      Start-Sleep 1
    }
  }
  default { Get-Content $MyInvocation.MyCommand.Path | Select-Object -Skip 2 -First 10; exit 1 }
}
