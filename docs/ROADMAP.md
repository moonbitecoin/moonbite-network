# MoonBite Roadmap

This roadmap separates **what is true today** from **what is planned**. Nothing
in the "Planned" sections is advertised on the website as a current feature —
that is a deliberate rule (see the "Honesty" principle below). Items move into
marketing copy only after they are implemented, tested, and verifiable.

Last updated: 2026-07-24.

---

## Shipped (true today)

- **Fair-launch consensus** — no premine, no presale, one public emission
  schedule. Capped at 19,999,999.87 MBITE; 10 MBITE reward halving every
  1,000,000 blocks. Implemented and unit/regtest-tested in the Litecoin Core
  fork.
- **scrypt proof-of-work** — the same PoW Litecoin has run since 2011
  (`src/primitives/block.cpp` → `GetPoWHash` → `scrypt_1024_1_1_256`).
- **Self-custodial wallet** — non-custodial key management; no accounts, no
  custodian.
- **MoonBite Reactor** — Windows desktop miner that mines the live chain via the
  node's mining endpoint.
- **Marketing site + block explorer** — Flask app live at moonbite.org (served
  from a DigitalOcean node).
- **Multi-node seed kit** — `deploy/seeds.txt`, `deploy/setup-node.sh`,
  `deploy/publish-node-binaries.sh` for standing up independent seed/full nodes.

## Honest status (what is NOT true yet)

- **Pre-mainnet.** Testnet + regtest only. No coin has market value; MBITE is not
  listed on any exchange and cannot be bought.
- **Not ASIC-resistant.** scrypt has a mature ASIC ecosystem (Litecoin/Dogecoin
  hardware).
- **No production security audit.** Experimental software.

---

## Planned — differentiators (design done, code NOT yet in tree)

These are the features that would make MoonBite meaningfully different from "a
Litecoin fork." They are **not implemented today** and must not be described as
if they were. Each needs real C++ work and its own test suite before it ships.

### P1 · RandomX proof-of-work (CPU-friendly, ASIC-resistant)

**Goal:** replace scrypt with RandomX so MoonBite is genuinely CPU-mineable and
ASIC-resistant (the Monero-style property the project originally aimed for).

**Why it matters:** it is the difference between "another scrypt coin that
Litecoin ASICs can dominate on day one" and "a coin ordinary people can mine on
the CPU they already own." This is the strongest available differentiator.

**Scope / cost (honest):**
- Swap `GetPoWHash` to call a RandomX hasher; link `librandomx` into the build
  (a full RandomX source tree already sits unintegrated at `/root/RandomX`).
- New genesis + fresh chain params (changing the PoW is a hard fork / relaunch,
  not an upgrade of the existing testnet).
- RandomX needs a large dataset in RAM and a seed-block cadence — affects node
  memory sizing and the mining/`getblocktemplate` path.
- Update every "scrypt" claim back to "RandomX" **only after** it is real.

**Status:** NOT started in the C++ tree. `/root/RandomX` is a stock clone, not
wired into the build. Today the daemon links no RandomX and hashes scrypt.

### P2 · SOS timelock claw-back vault

**Goal:** a self-custody vault that resists key theft. Funds sit in a P2WSH
script with two spend paths — an instant **recovery** key that claws funds back,
and a **hot** key that is time-locked (BIP68/112 CSV) for a delay window. If your
hot key is stolen, you use the recovery key to pull funds back before the thief's
delayed spend can confirm.

**Design (spec, not shipped):**
```
OP_IF   <recoveryPubKey> OP_CHECKSIG
OP_ELSE <delayBlocks> OP_CHECKSEQUENCEVERIFY OP_DROP <hotPubKey> OP_CHECKSIG
OP_ENDIF
```
Proposed wallet RPCs: `createvault`, `vaultstatus`, `sos` (sweep spendable
balance into a vault), `unvault`. Production delays 10/30/90 days =
5760/17280/51840 blocks at 2.5-min spacing.

**Why it matters:** a concrete, useful answer to "why hold MBITE over any other
fork" — built-in anti-theft that most chains don't offer at the wallet level.

**Fork constraints that shape the build (still true):** no miniscript; `raw()` is
TOP-only so `wsh(raw(...))` won't parse; the tx assembler forces one global
nSequence (no per-input) so `unvault` must build+sign the raw witness manually;
CSV delay must be pushed minimally (OP_N for 1–16) or MINIMALDATA rejects it;
`CWallet::IsSpent` takes this fork's `OutputIndex`
(`boost::variant<COutPoint, mw::Hash>`).

**Status:** NOT in the current tree. An earlier note claimed these RPCs were
committed (`ae6fa76`) and regtest-verified; verified on 2026-07-24 that no such
code, test, or commit exists in `/root/bigcoin-core` (HEAD `d8c8adc`). Treat this
as a design to implement, never as a shipped feature.

### P3 · In-browser miner

A real WASM miner (matching whatever PoW ships — scrypt today, RandomX under P1)
so the browser "Spark"/Reactor experience mines for real rather than triggering
server-side work. Currently the heavy PoW runs on the node, which the site states
honestly.

---

## Principle: honesty gates the roadmap

A feature earns a place in website copy, README tables, and marketing **only
after** it is implemented, tested, and independently verifiable. Until then it
lives here, under "Planned," described in the future tense. No fabricated
prices, volumes, exchange listings, or feature claims — ever. This rule is the
product, not an afterthought.
