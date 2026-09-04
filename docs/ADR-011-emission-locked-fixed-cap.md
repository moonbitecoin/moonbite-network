# ADR-011 — Emission is locked: fixed-cap, Bitcoin-style

- **Status:** Accepted
- **Date:** 2026-09-04
- **Related:** ADR-002 / ADR-010 (the emission schedule), ADR-006 (fair-launch
  and founder-mining disclosure), ADR-007 (no protocol revenue).

## Context

MoonBite's emission was set in ADR-010: a 10 MBITE block subsidy, halving every
1,650,000 blocks (about 6.27 years at 2-minute spacing), summing to a hard cap
just under 33,000,000 MBITE, with difficulty retargeting every 60 blocks and
RandomX proof of work.

Alternatives were weighed for a coin that hopes to become valuable over time:
a flatter/longer halving (spreads coins more evenly), and a tail emission
(a small permanent block reward that keeps miners paid forever, at the cost of
a fixed cap). The decision is to keep the Bitcoin-style fixed-cap model.

## Decision

**The emission schedule is fixed and will not be changed to chase a price.**
It stays exactly as ADR-010 defines it:

| Parameter | Value |
|---|---|
| Block subsidy | 10 MBITE, halving every 1,650,000 blocks |
| Block time | 2 minutes |
| Supply cap | ~32,999,999.96 MBITE (hard) |
| Proof of work | RandomX (CPU-friendly, ASIC-resistant) |

Rationale: a credible, unchangeable, scarce schedule is what lets a market
price the coin. Predictability is the asset. The network already adapts to
value on its own — if MoonBite becomes valuable, more miners arrive, difficulty
rises, and security scales up without any rule change; if it stays small,
difficulty falls and blocks still come every 2 minutes.

This is honestly front-loaded: roughly half of all coins are mined in the first
~6.3 years, and early solo mining (disclosed in ADR-006) accrues a large share
cheaply. That is inherent to the halving model and is accepted, not hidden.

## Miners earn two ways (no third, ever)

1. **Block subsidy** — new coins, on the schedule above.
2. **Transaction fees** — the fees of the transactions in the block.

There is no premine, no dev tax, no protocol fee (ADR-007). "Network fee" and
"miner fee" are the same thing, and it goes entirely to whoever mines the block.

## The one long-term risk, and the contingency

As halvings shrink the subsidy toward zero, miners must be paid by transaction
**fees** or network security weakens. The plan is to grow real usage so fee
revenue replaces the subsidy over time (Bitcoin's bet).

**Tail emission is a documented fallback, not a commitment.** If, by the time
the subsidy has become small, fee revenue has not grown enough to secure the
chain, a small permanent tail emission may be adopted — but only through a new
ADR, announced in advance, never silently. Until such an ADR exists, the cap is
hard and final.

## Consequences

- No code or genesis change: the chain already implements this schedule.
- The fixed-cap, hard-scarcity narrative is the official one.
- Any future change to emission requires a new ADR and public notice; there is
  no discretionary path to alter it.
