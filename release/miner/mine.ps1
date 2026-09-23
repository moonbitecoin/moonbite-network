# MoonBite solo miner - Windows (PowerShell).
#
# Solo and pool-free: runs a full MoonBite node on your PC and mines straight to
# YOUR wallet address. No pool, no account, no middleman.
#
#   .\mine.ps1 moon1youraddress   mine rewards to your wallet
#   .\mine.ps1                     use the saved address (or ask you for one)
#   .\mine.ps1 address             print the reward address in use
#   .\mine.ps1 stop                stop the node
#
# Get your address from the MoonBite wallet app (or moonbite.org/wallet):
# create a wallet, open Receive, copy the moon1... address.
param([string]$arg = "")
$ErrorActionPreference = "Stop"

$here    = Split-Path -Parent $MyInvocation.MyCommand.Path
$daemon  = Join-Path $here "moonbited.exe"
$clibin  = Join-Path $here "moonbite-cli.exe"
if (-not (Test-Path $daemon)) { Write-Error "moonbited.exe not found next to this script."; exit 1 }

$datadir = if ($env:MOONBITE_DATADIR) { $env:MOONBITE_DATADIR } else { Join-Path $env:USERPROFILE ".moonbite" }
$conf    = Join-Path $datadir "moonbite.conf"
$rewardFile = Join-Path $datadir "reward-address.txt"

function Invoke-Cli {
  # moonbite-cli is a native exe: a non-zero exit does not raise a PowerShell
  # error, so probe $LASTEXITCODE and throw ourselves. Without this every
  # "is the node up?" check silently succeeds and the node is never started.
  $out = & $clibin "-datadir=$datadir" "-conf=$conf" @args 2>&1
  if ($LASTEXITCODE -ne 0) { throw ("moonbite-cli failed: " + ($out | Out-String)) }
  $out | Where-Object { $_ -isnot [System.Management.Automation.ErrorRecord] }
}
function Test-Addr([string]$a) { return ($a -match '^moon1[0-9a-z]{20,88}$') }

function Get-P2pPort { if ($env:MOONBITE_P2P_PORT) { [int]$env:MOONBITE_P2P_PORT } else { 9444 } }
function Get-RpcPort { if ($env:MOONBITE_RPC_PORT) { [int]$env:MOONBITE_RPC_PORT } else { 9445 } }
function Test-PortListening([int]$port) {
  # Get-NetTCPConnection is missing on very old Windows; fall back to netstat.
  try { return [bool](Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction Stop) }
  catch { return [bool](netstat -ano | Select-String ":$port\s.*LISTENING") }
}

function Write-Conf {
  New-Item -ItemType Directory -Force -Path $datadir | Out-Null
  $pw = $null
  if (Test-Path $conf) { $pw = (Select-String -Path $conf -Pattern '^rpcpassword=(.*)$').Matches.Groups[1].Value }
  if (-not $pw) { $pw = -join ((1..48) | ForEach-Object { '{0:x}' -f (Get-Random -Max 16) }) }
  $p2p = if ($env:MOONBITE_P2P_PORT) { "port=$($env:MOONBITE_P2P_PORT)`n" } else { "" }
  $rpcp = if ($env:MOONBITE_RPC_PORT) { "rpcport=$($env:MOONBITE_RPC_PORT)`n" } else { "" }
  @"
server=1
listen=1
dbcache=512
rpcuser=moonminer
rpcpassword=$pw
$p2p${rpcp}addnode=67.205.154.64:9444
addnode=165.232.106.9:9444
"@ | Set-Content -Encoding ascii $conf
}
function Wait-Rpc {
  Write-Host " Starting the node..."
  for ($i=0; $i -lt 90; $i++) {
    try { Invoke-Cli getblockcount | Out-Null; return } catch {}
    if ($i -eq 4) { Write-Host " Still starting - the first run builds the RandomX cache, which can take a minute..." }
    Start-Sleep 2
  }
  throw "The node did not start. Check $datadir\debug.log for the reason."
}
function Start-Node {
  # Already have a reachable node (e.g. this script re-run)? Use it.
  try { Invoke-Cli getblockcount | Out-Null; return } catch {}
  # A node we can't authenticate to may already own the ports - typically a
  # second copy of this miner on the same PC. Only one node runs per machine;
  # launching another just fails to bind and hangs. Say so plainly and stop.
  if ((Test-PortListening (Get-P2pPort)) -or (Test-PortListening (Get-RpcPort))) {
    Write-Host ""
    Write-Host "  A MoonBite node is already running on this computer"
    Write-Host "  (network port $(Get-P2pPort) is in use). You are already mining -"
    Write-Host "  only one node runs per machine, so this window isn't needed."
    Write-Host ""
    Write-Host "  To run a SECOND, separate miner here on purpose, give it its own"
    Write-Host "  ports and data folder first, for example:"
    Write-Host '      $env:MOONBITE_P2P_PORT=19444; $env:MOONBITE_RPC_PORT=19445'
    Write-Host '      $env:MOONBITE_DATADIR="$env:USERPROFILE\.moonbite2"'
    Write-Host "      .\mine.ps1"
    Write-Host ""
    exit 0
  }
  Write-Conf
  Start-Process -FilePath $daemon -ArgumentList "-datadir=$datadir","-conf=$conf" -WindowStyle Hidden | Out-Null
  Wait-Rpc
}

function Resolve-Reward([string]$cand) {
  # Priority: CLI arg, env var, a previously saved address - then, with none of
  # those, no prompt and no wallet app required: the node has its own built-in
  # wallet (createwallet + getnewaddress), so mining starts with zero setup.
  # Bringing an address from the wallet app stays fully optional, not required.
  if ($cand -and (Test-Addr $cand)) { Set-Content -Encoding ascii $rewardFile $cand; return $cand }
  if ($env:MOONBITE_ADDRESS -and (Test-Addr $env:MOONBITE_ADDRESS)) { Set-Content -Encoding ascii $rewardFile $env:MOONBITE_ADDRESS; return $env:MOONBITE_ADDRESS }
  if (Test-Path $rewardFile) { $a = (Get-Content $rewardFile -Raw).Trim(); if (Test-Addr $a) { return $a } }
  try { Invoke-Cli createwallet "miner" | Out-Null } catch { try { Invoke-Cli loadwallet "miner" | Out-Null } catch {} }
  $a = (Invoke-Cli -rpcwallet=miner getnewaddress "mining" | Out-String).Trim()
  if (-not (Test-Addr $a)) { throw "Could not create a mining wallet on this node." }
  Set-Content -Encoding ascii $rewardFile $a
  Write-Host "No wallet address given, so this node made you one: $a"
  Write-Host "That's a real MoonBite address, held in this node's own wallet on this machine."
  Write-Host "Import it into the wallet app anytime to spend from it - moonbite.org/wallet."
  Write-Host "(Already have a wallet? Run .\mine.ps1 moon1youraddress to mine straight into it.)"
  return $a
}

switch ($arg) {
  "stop" {
    Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*moonbite-cli*generatetoaddress*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    try { Invoke-Cli stop } catch {}
    for ($i=0; $i -lt 20; $i++) { if (-not (Get-Process moonbited -ErrorAction SilentlyContinue)) { break }; Start-Sleep 2 }
    Get-Process moonbited -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "stopped."
  }
  "address" { Start-Node; Write-Host "Rewards go to: $(Resolve-Reward '')" }
  default {
    Start-Node
    $addr = Resolve-Reward $arg
    Write-Host "======================================================================"
    Write-Host " MoonBite solo miner"
    Write-Host " Rewards to: $addr"
    Write-Host " Ctrl-C to stop. Coins are spendable 100 blocks after being mined."
    Write-Host "======================================================================"
    Write-Host " Syncing with the network before mining..."
    while ($true) {
      try {
        $info = Invoke-Cli getblockchaininfo | Out-String | ConvertFrom-Json
        if ($info -and -not $info.initialblockdownload -and $info.blocks -ge $info.headers) { break }
        Write-Host "   ...$($info.blocks) / $($info.headers) blocks"
      } catch {}
      Start-Sleep 3
    }
    Write-Host " Synced at height $(Invoke-Cli getblockcount). Mining now."
    $found = 0
    while ($true) {
      try {
        $tries = if ($env:MAXTRIES) { $env:MAXTRIES } else { "100000" }
        $out = ""
        try { $out = (Invoke-Cli generatetoaddress 1 $addr $tries | Out-String) } catch {}
        if ($out -match '[0-9a-f]{64}') { $found++; Write-Host "  BLOCK FOUND!  height $(Invoke-Cli getblockcount)   (found $found this session)   peers $(Invoke-Cli getconnectioncount)" }
      } catch {
        Write-Host "  (rpc hiccup) retrying..."; Start-Sleep 5
      }
      Start-Sleep 1
    }
  }
}
