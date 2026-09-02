# ADR-010 — 2-minute blocks, 60-block retarget, 10 MBITE subsidy

- **Status:** Accepted
- **Date:** 2026-09-02
- **Supersedes:** the 10-minute / 50 MBITE / 330,000-block / 2016-block-retarget
  parameters previously baked into chainparams and documented across the site.
- **Superseded by:** —
- **Related:** ADR-001 (RandomX proof-of-work), ADR-006 (fair launch and founder
  early-mining disclosure), ADR-007 (no protocol revenue, governance freeze).

## Context

The launch parameters were a straight Bitcoin transplant: a 10-minute block
target, a 50 MBITE subsidy, halving every 330,000 blocks, and difficulty
retargeting every 2016 blocks (about 14 days) with the usual 4x clamp.

Two problems surfaced once we ran the numbers for a young chain:

1. **A 10-minute chain with a handful of miners feels dead.** With few miners
   and a first confirmation ten minutes away on average, the explorer sits
   still, wallets show "unconfirmed" for long stretches, and the network gives
   nobody a reason to believe it is alive. The bootstrap period is exactly when
   the chain most needs visible motion.

2. **A 2016-block retarget locks the early difficulty in place for two weeks.**
   Difficulty starts at the floor and does not move until block 2016. If a
   hundred early miners show up on day one, they collectively produce blocks
   every few seconds — at 10 minutes per block the first retarget would not
   even arrive for weeks of wall-clock time — and the whole first difficulty
   epoch is handed to whoever got there first. That is an instamine window, and
   it is the opposite of the fair launch ADR-006 promises.

A very short block time (3 seconds) was considered and rejected: at that
spacing, ordinary P2P propagation latency across the Internet is comparable to
the block interval, so most blocks would be orphaned and the chain would spend
its hash power fighting itself rather than securing history.

## Decision

Re-genesis the chain (mainnet, testnet and regtest) with the following
consensus parameters:

| Parameter | Old | New |
|---|---|---|
| Target block time | 10 minutes (600 s) | **2 minutes (120 s)** |
| Block subsidy | 50 MBITE | **10 MBITE** |
| Halving interval | 330,000 blocks | **1,650,000 blocks** |
| Difficulty retarget | every 2016 blocks (~14 days), 4x clamp | **every 60 blocks (~2 hours), 4x clamp** |
| Minimum difficulty (genesis `nBits`) | `0x1e0ffff0` | **`0x1f0ffff0`** (easier floor) |
| Coinbase maturity | 100 blocks | 100 blocks (unchanged) |

The easier difficulty floor means a single CPU produces blocks in seconds at
launch; the 60-block retarget then pulls difficulty up to the real hash rate
within the first few hours instead of the first few weeks.

## Consequences

- **Emission is unchanged.** 10 MBITE every 2 minutes is the same 300 MBITE per
  hour as 50 MBITE every 10 minutes. The supply cap stays just under
  33,000,000 MBITE (32,999,999.96), and a halving still lands roughly every
  6.27 years — 1,650,000 blocks at 2 minutes is the same span of time as
  330,000 blocks at 10 minutes.
- **Coinbase maturity is ~200 minutes** (100 blocks × 2 minutes) instead of
  ~1000 minutes. Freshly mined coins become spendable in a little over three
  hours.
- **Confirmation guidance changes.** Six confirmations is about 12 minutes; the
  exchange-listing recommendation of 12+ confirmations is about 24 minutes.
- **Re-genesis.** The genesis blocks (and therefore every hash on the existing
  chain) are re-mined. Nothing mined on the old parameters carries over; nodes
  on the old build are on a different network and will not sync. The shipped
  binaries, `release/README.md`, and the deploy kit must be rebuilt/updated
  against the new genesis hashes.
- **The early-miner advantage still exists and is disclosed.** Difficulty
  adapts in hours, not weeks, so the window is far smaller — but whoever mines
  in the first hours after launch still gets cheap blocks. Per ADR-006, any
  founder or early mining is disclosed publicly rather than hidden; this ADR
  does not change that obligation, it only shrinks the window.
- **Faster blocks mean more orphans than a 10-minute chain**, but at 2 minutes
  the orphan rate stays in the range Litecoin-lineage chains have run for
  years. It is the compromise between "feels alive" and "propagates cleanly".
- **Higher block count per year** (~262,800 blocks/year vs ~52,560): block
  height grows five times faster, and anything that reasoned in block counts
  (vault delays, checkpoints, halving countdowns) must be re-expressed for
  2-minute spacing.
- All docs and site copy that quoted the old figures are updated alongside this
  ADR. Halving is described in blocks *and* years so readers can see the time
  schedule did not move.
