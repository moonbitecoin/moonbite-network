# MoonBite CPU Miner

A standalone miner — **separate from the wallet**. It runs a MoonBite full node
on your own computer, connects to the network, and mines with your **CPU** to a
reward address you choose. The node does the real RandomX proof-of-work, so this
is genuine mining: no browser tricks, and no server mining on your behalf.

## Start mining (one command)

**Windows** — double-click `Start-Miner.bat`, or in a terminal:

```
python moonbite-miner.py --address moon1yourrewardaddress
```

**Linux / macOS**:

```
./start-miner.sh --address moon1yourrewardaddress
```

Leave off `--address` and it will ask. That address is the **only** thing that
decides where your coins go — the miner never asks for, sees, or stores a seed
phrase or private key.

## What it does

1. Finds the `moonbited` node binary (next to this app, in a `bin/` folder, in
   the repo's `release/miner/`, or on your PATH — or pass `--node <path>`).
2. Writes a private-by-default config that dials the network seeds.
3. Starts the node and waits for it to sync the chain.
4. Mines to your address, printing each block found and a live rate.
5. Stops the node cleanly on `Ctrl+C`.

## Requirements (honest)

- **~3.3 GB of free RAM.** RandomX (the proof-of-work) reserves that much. A
  normal laptop or desktop is fine; a small cloud VPS is not (the OS will kill
  it). The miner warns you if RAM looks tight.
- **First-run sync.** Before mining can start, the node downloads and verifies
  the chain. This can take a while — leave it running.
- **Python 3** and the **`moonbited` node binary** for your OS. Get the signed
  binary from https://moonbite.org/download and verify it against the published
  signature (see `deploy/RELEASE-SIGNING.md`).

## Options

| Flag | Meaning | Default |
|------|---------|---------|
| `--address` | Reward address (also `MINE_ADDRESS` env) | *(prompted)* |
| `--node` | Path to `moonbited` (also `MOONBITE_NODE`) | auto-detect |
| `--datadir` | Chain data dir (also `MOONBITE_DATADIR`) | per-OS app dir |
| `--seeds` | Seed `host:port` list (also `MOONBITE_SEEDS`) | the live seed |
| `--rpc-port` | Local node RPC port | 9445 |
| `--blocks N` | Stop after N blocks | 0 (forever) |
| `--maxtries N` | PoW attempts per round | 1,000,000 |

## Is this "real" mining?

Yes. MoonBite uses RandomX, a CPU-friendly proof-of-work. Your node's CPU
computes the proof-of-work and, when it finds a valid block, the reward is paid
to your address on-chain. A web page **cannot** do this (it can't run RandomX at
useful speed), which is why the miner is a real node and not a browser gadget.

For maximum multi-core throughput on a busy chain you would eventually point a
dedicated RandomX miner at the node via `getblocktemplate`; for launching and
mining MoonBite today, this local-node miner is the honest, simple path.

## Safety

- Non-custodial: no keys or seed phrases are ever handled here.
- The node's RPC is bound to `127.0.0.1` only, with a random password.
- Your reward address and chain data stay on your machine.
