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

function Invoke-Cli { & $clibin "-datadir=$datadir" "-conf=$conf" @args }
function Test-Addr([string]$a) { return ($a -match '^moon1[0-9a-z]{20,88}$') }

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
  Start-Process -FilePath $daemon -ArgumentList "-datadir=$datadir","-conf=$conf" -WindowStyle Hidden | Out-Null
  Wait-Rpc
}

function Resolve-Reward([string]$cand) {
  if ($cand -and (Test-Addr $cand)) { Set-Content -Encoding ascii $rewardFile $cand; return $cand }
  if ($env:MOONBITE_ADDRESS -and (Test-Addr $env:MOONBITE_ADDRESS)) { Set-Content -Encoding ascii $rewardFile $env:MOONBITE_ADDRESS; return $env:MOONBITE_ADDRESS }
  if (Test-Path $rewardFile) { $a = (Get-Content $rewardFile -Raw).Trim(); if (Test-Addr $a) { return $a } }
  Write-Host "Paste the MoonBite wallet address to receive your mining rewards"
  Write-Host "(from the wallet app / moonbite.org/wallet - Receive tab, moon1...):"
  $a = (Read-Host).Trim()
  if (Test-Addr $a) { Set-Content -Encoding ascii $rewardFile $a; return $a }
  throw "That did not look like a moon1 address."
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
