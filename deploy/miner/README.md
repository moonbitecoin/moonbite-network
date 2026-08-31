# Mining MoonBite

## Why this is a separate machine

Neither seed node can mine.

RandomX reserves roughly **3.3 GB** of address space. The DigitalOcean seed has
**458 MB** of RAM and 2 GB of swap, and was still OOM-killed mid-block:

```
Out of memory: Killed process (moonbited) total-vm:3388296kB
moonbited.service: Failed with result 'oom-kill'
```

The Railway container is smaller again. Adding swap did not help — RandomX
touches its dataset randomly by design, so swapping it is not slow, it is
unusable. The seeds stay as seeds: always-on, publicly reachable, relaying.
Mining happens on a host with real memory and reaches the network over ordinary
P2P.

## Running it

```bash
export MOONBITE_SRC=/root/bigcoin-core/src   # where litecoind/litecoin-cli live
./moonbite-miner.sh start        # node up, dials the seeds
./moonbite-miner.sh mine 10      # mine 10 blocks (omit the count = forever)
./moonbite-miner.sh status       # height, peers, balance
./moonbite-miner.sh stop
```

Blocks pay a single stable address, recorded in `$MOONBITE_DATADIR/mining-address.txt`,
so a run's coinbase history is one auditable line instead of a scatter of
addresses. The wallet lives in the datadir — **back it up**, or the coins are
gone with the machine.

### Environment

| Variable | Default | Meaning |
|---|---|---|
| `MOONBITE_SRC` | `/root/bigcoin-core/src` | directory holding the built binaries |
| `MOONBITE_DATADIR` | `~/.moonbite` | chain data and wallet |
| `MOONBITE_SEEDS` | the two live seeds | comma-separated `host:port` to dial |

## The miner is usually behind NAT

That is fine — it dials out to the seeds rather than waiting to be dialled, and
a mined block is announced over that same connection.

One caveat worth knowing, because it cost an afternoon: while the seed's only
outbound peer was dead, the seed was stuck in initial block download against
that dead peer and would not fetch blocks announced by anyone else. It parked
the header (`getchaintips` showed `"status": "headers-only"`) with an empty
download queue and sat there. **A seed with no healthy outbound peer does not
sync, no matter who is talking to it.** If blocks stop propagating, check the
seeds' peer lists before suspecting the miner.

## Fair launch

Every block mined here is real supply on the live chain, paid to the address
above. Per ADR-006 any pre-announcement mining is disclosed rather than quiet.
If these blocks are not meant to be part of the launch distribution, reset the
chain to genesis *before* anything is built on top of it — once wallets hold
balances derived from this coinbase, unwinding it means a reorg, not a delete.
