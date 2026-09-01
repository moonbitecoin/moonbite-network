# MoonBite Core — Release Binaries

MoonBite (**MBITE**) is a proof-of-work Layer-1 coin, forked from Litecoin Core v0.21.5.5.
These are Linux x86-64 binaries built on Ubuntu 22.04 (glibc 2.35).

## Chain parameters

| Parameter        | Value                        |
|------------------|------------------------------|
| Ticker           | MBITE                          |
| PoW algorithm    | RandomX (CPU-friendly, ASIC-resistant) |
| Max supply       | just under 33,000,000 MBITE  |
| Block time       | 10 minutes                   |
| Initial reward   | 50 MBITE                     |
| Halving interval | 330,000 blocks (~6.27 years) |
| Address prefix   | bech32 `moon1…` (testnet `tmoon1…`, regtest `rmoon1…`); legacy P2PKH `M`, P2SH `3` |
| P2P port         | 9444 (mainnet) / 19555 (testnet) / 19444 (regtest) |
| RPC port         | 9445 (mainnet) / 19445 (testnet) / 19443 (regtest) |

### Genesis blocks (baked in)
- **mainnet** `2a5ae28180448a88bdd89f2cca926ce6e82d5e8eda787ede03ee244aa0aad4ea` (nonce 287032)
- **testnet** `67afe8001e52e947b27d201dd2768839dd79b6cf6d259f123172f4f428a3cd5d` (nonce 217889)
- **regtest** `e5e666e9b7813a408f078a6dd8fb1457c3aed176493b99b2278d85031b259f7d` (nonce 2)

## Contents (`bin/`)
- `moonbited` — full node daemon
- `moonbite-cli` — RPC command-line client
- `moonbite-qt` — **desktop GUI wallet** (Qt5)
- `moonbite-tx` — raw transaction utility
- `moonbite-wallet` — offline wallet tool

### Windows x86-64 (`bin/*.exe`)
- `moonbited.exe`, `moonbite-cli.exe`, `moonbite-tx.exe`, `moonbite-wallet.exe`
- Cross-built with mingw-w64 (POSIX threads, static libstdc++/winpthread). Depend only on
  system DLLs (kernel32, ws2_32, advapi32, shell32, iphlpapi, msvcrt) — no runtime installer needed.
- Headless build: no `moonbite-qt.exe` yet.
- Verified on Windows 11: daemon starts, mines RandomX regtest blocks, shuts down cleanly.
- `miner/mine.ps1` expects `moonbited.exe` and `moonbite-cli.exe` next to it; copy them in or
  point the script at `bin/`.

Verify downloads against `SHA256SUMS.txt`.

## Desktop wallet
Launch the GUI wallet with `./bin/moonbite-qt` (mainnet) or `./bin/moonbite-qt -testnet`.
It runs an integrated node and reports client name `MoonBiteCore` on the network.

## Quick start (regtest — instant local mining)
```bash
./bin/moonbited -regtest -rpcuser=big -rpcpassword=big -daemon
CLI="./bin/moonbite-cli -regtest -rpcuser=big -rpcpassword=big"
$CLI createwallet "wallet"
ADDR=$($CLI getnewaddress)
$CLI generatetoaddress 101 "$ADDR"   # mine 101 blocks (coinbase matures at 100)
$CLI getbalance                      # -> 50.00000000
$CLI sendtoaddress <dest_addr> 12.5  # send MBITE
$CLI stop
```

## Mainnet / testnet
1. Copy `moonbite.conf.example` → data dir as `moonbite.conf`, set a strong `rpcpassword`.
2. `./bin/moonbited` (mainnet) or `./bin/moonbited -testnet`.
3. See the repo `docs/` for mining, wallet, node-setup, and exchange-listing guides.

## Verified working
- **Mining:** RandomX PoW, regtest mined 101 blocks → 50 MBITE coinbase matured.
- **Transactions:** send/receive confirmed (12.5 MBITE between two wallets, mempool → block).
- **P2P networking:** two nodes connect and sync a 10-block chain (identical tips).
- **Wallet security:** AES-256 encryption, passphrase-locked spending, HD seed, backup — all verified.
- **Block explorer:** wired to a live node, serves real block/tx data (no demo mode).
- **Branding:** `--version` reports **MoonBite Core**; window title / About dialog say
  "MoonBite Core"; network client name `MoonBiteCore` (`/MoonBiteCore:0.21.5.5/`);
  default data directory is `.moonbite` (Linux) / `MoonBite` (Windows/macOS).

## Status / known remaining polish
- Mainnet has no DNS seeds yet (removed Litecoin's); use `deploy/` to stand up seed
  nodes on VPS hosts, then bake their IPs into chainparams before public launch.
- A few deep-menu Qt labels may still read "Litecoin" (cosmetic); core identity,
  version banner, About dialog, and data dir are all MoonBite.
- macOS/Windows native builds require cross-compiling (these are Linux x86-64).

Forked chain — **not** affiliated with or compatible with the Litecoin network
(distinct magic bytes, ports, genesis, and address prefixes).
