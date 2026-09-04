# ADR-006 — Fair launch and founder early-mining disclosure

- **Status:** Accepted
- **Date:** 2026-09-03 (disclosure written the day the chain went live)
- **Related:** ADR-002 (emission), ADR-007 (no protocol revenue), ADR-010 (2-minute blocks, re-genesis)

## Decision

MoonBite launches with no premine, no founder allocation, no dev tax and no
hidden mining advantage. Every MBITE that exists was produced by the public
proof-of-work rules in the public source code. The miner the founder runs is
the same `moonbited` binary that is published for download; there is no faster
private build.

What a fair launch cannot avoid is that somebody mines the first blocks. This
document records exactly who did, with what, and how much, so that nobody has
to take it on trust.

## Disclosure

| | |
|---|---|
| Chain | mainnet genesis `3d053c590c9dcaa972d12f20793cde15e060f6cbcd1ea7bd05f4c80724f39573` |
| Go-live | 2026-09-02 21:40 UTC (block 1) |
| Founder mining address | not published at this time |
| Hardware | one desktop PC, 6 CPU cores, the published Windows build |
| Blocks mined by the founder | every block from 1 up to the moment other miners join (196 at the time of writing) |
| Reward per block | 10 MBITE (ADR-010) |
| Founder holdings at the time of writing | 1,960 MBITE, all from block rewards, 1,000 of it still immature |
| Share of the 33,000,000 MBITE cap | under 0.006 % |

The seed node on the network does not mine. Anyone can verify the figures
above with the public explorer (`/api/explorer/blocks`) or their own node:
every coinbase output up to the point other miners appear pays the address
listed here.

## Earlier chains

Two earlier mainnets (genesis `2a5ae281…` and `cabdebc6…`) were abandoned
before public announcement when the block-time and difficulty parameters were
changed (ADR-010). Nothing mined on them exists on this chain. Their data
directories are archived, not carried forward.

## Commitments

- Founder-mined coins stay at the address above. Any movement out of it will
  be announced in a new ADR before it happens.
- Any change to these commitments will be recorded as a new ADR before it
  happens, never after.
- This file will be updated with the block height at which the first
  non-founder miner produced a block, once that happens.
