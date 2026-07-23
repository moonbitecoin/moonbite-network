# Mining BigCoin (BIG)

BigCoin is a RandomX proof-of-work coin (a Litecoin/Bitcoin Core fork). This guide
covers testing your setup on regtest, solo mining, CPU mining, and joining a
pool.

## Key network parameters

| Parameter              | Value                         |
|------------------------|-------------------------------|
| PoW algorithm          | RandomX (CPU-optimized)       |
| Target block time      | 2.5 minutes (150 s)           |
| Initial block reward   | 10 BIG                        |
| Halving interval       | every 1,000,000 blocks        |
| Max supply             | 19,999,999.87 BIG             |
| Mainnet P2P port       | 9444                          |
| Testnet P2P port       | 19555                         |
| RPC default port       | 9445                          |

> Because BigCoin uses **RandomX** (like Monero), it is CPU-optimized and
> ASIC-resistant. Mine it with a CPU using a RandomX-capable miner — SHA-256
> ASICs and GPU miners have little to no advantage on RandomX.

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

## 2. CPU mining with a RandomX miner

RandomX is a CPU-optimized proof-of-work. You mine it with a RandomX-capable
CPU miner (the xmrig-class of RandomX miners) speaking the stratum protocol to a
pool. GPUs and ASICs have little to no advantage over CPUs on RandomX, so a
modern multi-core CPU with enough RAM (RandomX uses a large dataset) is the
right tool.

Build/obtain a RandomX-capable CPU miner:

```bash
# TODO: exact RandomX miner + build steps for BigCoin TBD
# (a RandomX/xmrig-class CPU miner pointed at a BigCoin RandomX stratum pool)
```

### CPU mining against a pool (stratum)

```bash
# TODO: exact RandomX miner command line for BigCoin TBD
# Point your RandomX CPU miner at the pool's stratum endpoint:
#   --url=stratum+tcp://POOL_HOST:POOL_PORT
#   --user=YOUR_BIG_ADDRESS.workername
#   --pass=x
```

Replace `POOL_HOST:POOL_PORT` with your pool's stratum endpoint, and
`YOUR_BIG_ADDRESS` with a BigCoin address (starts with `B`, or a bech32
`big1...` address). Many pools use `address.worker` as the username and `x` as
the password.

### CPU "solo" mining via a local stratum bridge

The core daemon speaks JSON-RPC (`getblocktemplate`), **not** stratum. RandomX
CPU miners speak stratum. To solo mine you need a small stratum bridge/proxy
that translates between the two — for example a lightweight solo pool or a
`getblocktemplate` proxy that supports RandomX. Point the bridge at your
`bigcoind` RPC (port 9445) and point your RandomX miner at the bridge:

```bash
# 1) run bigcoind with RPC enabled (see NODE_SETUP.md)
# 2) run a getblocktemplate->stratum bridge (RandomX) pointed at 127.0.0.1:9445
# 3) point your RandomX CPU miner at the bridge:
# TODO: exact RandomX miner command + a RandomX-aware getblocktemplate/stratum
#       bridge for BigCoin TBD
#   --url=stratum+tcp://127.0.0.1:3333
#   --user=YOUR_BIG_ADDRESS
#   --pass=x
```

---

## 3. Joining a mining pool

A pool aggregates many miners' hash power and pays out proportionally, smoothing
your rewards. To join, you point any RandomX CPU miner at the pool's stratum URL.

Stratum URL format (placeholder — use your pool's real values):

```
stratum+tcp://<pool-host>:<stratum-port>
```

Typical worker credentials:

| Field    | Value                                            |
|----------|--------------------------------------------------|
| Username | `YOUR_BIG_ADDRESS.workername`                    |
| Password | `x` (or whatever the pool specifies)             |
| Algo     | `randomx`                                         |

Example:

```bash
# TODO: exact RandomX miner command line for BigCoin TBD
# Point your RandomX CPU miner at the pool:
#   --url=stratum+tcp://big-pool.example.com:3333
#   --user=BqExampleAddressXXXXXXXXXXXXXXXXXXXX.rig1
#   --pass=x
```

Because BigCoin is new, there may be no public pools yet. Early on you may need
to run your own solo pool (RandomX-capable) as described in section 2.

---

## 4. Profitability — an honest note

There are **no profit promises here.** Whether mining earns anything at all
depends entirely on:

- **Network difficulty** — rises as more hash power joins; your share of blocks
  falls accordingly.
- **BIG's market price** — which may be zero, illiquid, or nonexistent for a new
  coin.
- **Your electricity cost and hardware efficiency.**

What is true of new networks:

- **Early networks have very low difficulty.** When few miners are online, even a
  single CPU can find blocks. This is by design and is temporary.
- As hash power grows, difficulty retargets upward and per-miner rewards drop.
- Do not spend money on hardware or electricity expecting a return. Treat early
  mining as experimentation and network bootstrapping, not investment.

BigCoin is experimental software. Mine it to help secure and bootstrap the
network and to learn — not because you are promised a payout.
