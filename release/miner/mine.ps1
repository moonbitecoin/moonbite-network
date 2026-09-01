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

function Cli { & $clibin "-datadir=$datadir" "-conf=$conf" @args }

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
addnode=hayabusa.proxy.rlwy.net:14389
"@ | Set-Content -Encoding ascii $conf
}

function Wait-Rpc { for ($i=0; $i -lt 60; $i++) { try { Cli getblockcount | Out-Null; return } catch { Start-Sleep 2 } } throw "node did not start" }

function Start-Node {
  try { Cli getblockcount | Out-Null; return } catch {}
  Write-Conf
  & $daemon "-datadir=$datadir" "-conf=$conf" "-daemon" | Out-Null
  Wait-Rpc
}

function Ensure-Wallet { try { Cli createwallet $wallet | Out-Null } catch { try { Cli loadwallet $wallet | Out-Null } catch {} } }

function Mining-Address {
  $f = Join-Path $datadir "mining-address.txt"
  if (Test-Path $f) { return (Get-Content $f -Raw).Trim() }
  $a = Cli "-rpcwallet=$wallet" getnewaddress "mining"
  Set-Content -Encoding ascii $f $a; return $a
}

switch ($cmd) {
  "address" { Start-Node; Ensure-Wallet; Write-Host "Your mining address: $(Mining-Address)" }
  "stop"    { try { Cli stop } catch {}; Write-Host "stopped." }
  "mine"    {
    Start-Node; Ensure-Wallet
    $addr = Mining-Address
    Write-Host "======================================================================"
    Write-Host " MoonBite solo miner"
    Write-Host " Mining to: $addr"
    Write-Host " Wallet:    $datadir\$wallet   (back this up)"
    Write-Host " Ctrl-C to stop. Coins are spendable 100 blocks after being mined."
    Write-Host "======================================================================"
    $found = 0
    while ($true) {
      $h0 = [int](Cli getblockcount)
      $tries = if ($env:MAXTRIES) { $env:MAXTRIES } else { "100000" }
      try { Cli "-rpcwallet=$wallet" generatetoaddress 1 $addr $tries | Out-Null } catch {}
      $h1 = [int](Cli getblockcount)
      if ($h1 -gt $h0) { $found++; Write-Host "  BLOCK FOUND!  height $h1   (found $found this session)   peers $(Cli getconnectioncount)" }
      Start-Sleep 1
    }
  }
  default { Get-Content $MyInvocation.MyCommand.Path | Select-Object -Skip 2 -First 10; exit 1 }
}
