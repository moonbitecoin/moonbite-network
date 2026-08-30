# Mining MoonBite (MBITE)

MoonBite is a RandomX proof-of-work coin (a Litecoin/Bitcoin Core fork). This guide
covers testing your setup on regtest, solo mining, mining, and joining a
pool.

## Key network parameters

| Parameter              | Value                         |
|------------------------|-------------------------------|
| PoW algorithm          | RandomX (CPU-optimised)       |
| Target block time      | 10 minutes (600 s)            |
| Initial block reward   | 50 MBITE                      |
| Halving interval       | every 330,000 blocks          |
| Max supply             | 32,999,999.96 MBITE           |
| Mainnet P2P port       | 9444                          |
| Testnet P2P port       | 19555                         |
| RPC default port       | 9445                          |

> MoonBite uses **RandomX** — the CPU-optimised proof-of-work Monero has run
> since 2019. RandomX is deliberately hostile to GPUs and ASICs: the fastest
> practical miner is an ordinary desktop CPU, which keeps mining open to anyone
> with a computer rather than concentrating it in hardware farms.

---

## 1. Solo mining on regtest (for testing)

`regtest` is a private, local network where you control block production. It is
the right place to verify your build, wallet, and mining pipeline before touching
mainnet/testnet. On regtest, blocks are generated instantly and difficulty is
trivial.

Start the daemon in regtest mode:

```bash
bigcoind -regtest -daemon -server \
  -rpcuser=youruser -rpcpassword=yourpass
```

Create an address to receive the coinbase reward and mine to it:

```bash
# create/receive address
ADDR=$(bigcoin-cli -regtest getnewaddress)

# mine 101 blocks to that address
# (coinbase outputs need 100 confirmations before they are spendable)
bigcoin-cli -regtest generatetoaddress 101 "$ADDR"

# check that the reward is now spendable
bigcoin-cli -regtest getbalance
```

### getblocktemplate (the "real" mining path)

`generatetoaddress` is a convenience RPC. Real miners (pools, external miners)
use `getblocktemplate` to fetch work, then submit solved blocks with
`submitblock`:

```bash
# fetch a block template
bigcoin-cli -regtest getblocktemplate '{"rules": ["segwit"]}'

# ... your miner builds the block header, finds a nonce whose
#     RandomX hash meets the target, serializes the block ...

bigcoin-cli -regtest submitblock <hex-encoded-block>
```

For local testing you almost always just use `generatetoaddress`. Use
`getblocktemplate`/`submitblock` when integrating an external miner or pool.

> **Note:** `generatetoaddress` also works on regtest for testnet-style dry runs.
> On **mainnet/testnet** the daemon will not "generate" blocks for you at any
> useful rate — real difficulty applies and you must use an actual miner (below).

---

## 2. Mining with an external RandomX miner

RandomX is mined with a RandomX-capable miner speaking the stratum protocol to a
pool. Because RandomX is the Monero algorithm, the existing CPU tooling works:
CPU miners such as **XMRig**. There are no viable RandomX ASICs — a CPU is
the hardware.

Build/obtain a RandomX miner:

```bash
# TODO: exact RandomX miner + build steps for MoonBite TBD
# (e.g. an XMRig build pointed at a MoonBite stratum pool)
```

### Mining against a pool (stratum)

```bash
# TODO: exact RandomX miner command line for MoonBite TBD
# Point your RandomX miner at the pool's stratum endpoint:
#   --algo=rx/0
#   --url=stratum+tcp://POOL_HOST:POOL_PORT
#   --user=YOUR_MBITE_ADDRESS.workername
#   --pass=x
```

Replace `POOL_HOST:POOL_PORT` with your pool's stratum endpoint, and
`YOUR_MBITE_ADDRESS` with a MoonBite address (a bech32
`moon1...` address). Many pools use `address.worker` as the username and `x` as
the password.

### CPU "solo" mining via a local stratum bridge

The core daemon speaks JSON-RPC (`getblocktemplate`), **not** stratum. RandomX
miners speak stratum. To solo mine you need a small stratum bridge/proxy
that translates between the two — for example a lightweight solo pool or a
`getblocktemplate` proxy that supports RandomX. Point the bridge at your
`bigcoind` RPC (port 9445) and point your RandomX miner at the bridge:

```bash
# 1) run bigcoind with RPC enabled (see NODE_SETUP.md)
# 2) run a getblocktemplate->stratum bridge (RandomX) pointed at 127.0.0.1:9445
# 3) point your RandomX miner at the bridge:
# TODO: exact RandomX miner command + a getblocktemplate/stratum
#       bridge for MoonBite TBD
#   --algo=rx/0
#   --url=stratum+tcp://127.0.0.1:3333
#   --user=YOUR_MBITE_ADDRESS
#   --pass=x
```

---

## 3. Joining a mining pool

A pool aggregates many miners' hash power and pays out proportionally, smoothing
your rewards. To join, you point any RandomX miner at the pool's stratum URL.

Stratum URL format (placeholder — use your pool's real values):

```
stratum+tcp://<pool-host>:<stratum-port>
```

Typical worker credentials:

| Field    | Value                                            |
|----------|--------------------------------------------------|
| Username | `YOUR_MBITE_ADDRESS.workername`                    |
| Password | `x` (or whatever the pool specifies)             |
| Algo     | `rx/0` (RandomX)                                          |

Example:

```bash
# TODO: exact RandomX miner command line for MoonBite TBD
# Point your RandomX miner at the pool:
#   --algo=rx/0
#   --url=stratum+tcp://pool.example.com:3333
#   --user=moon1exampleaddressxxxxxxxxxxxxxxxxxxxx.rig1
#   --pass=x
```

Because MoonBite is new, there may be no public pools yet. Early on you may need
to run your own solo pool (RandomX-capable) as described in section 2.

---

## 4. Profitability — an honest note

There are **no profit promises here.** Whether mining earns anything at all
depends entirely on:

- **Network difficulty** — rises as more hash power joins; your share of blocks
  falls accordingly.
- **MBITE's market price** — which may be zero, illiquid, or nonexistent for a new
  coin.
- **Your electricity cost and hardware efficiency.**

What is true of new networks:

- **Early networks have very low difficulty.** When few miners are online, even a
  single CPU can find blocks. This is by design and is temporary.
- As hash power grows, difficulty retargets upward and per-miner rewards drop.
- Do not spend money on hardware or electricity expecting a return. Treat early
  mining as experimentation and network bootstrapping, not investment.

MoonBite is experimental software. Mine it to help secure and bootstrap the
network and to learn — not because you are promised a payout.
