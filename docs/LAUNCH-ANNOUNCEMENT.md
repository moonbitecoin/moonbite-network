# MoonBite mainnet launch — announcement kit (2026-09-21)

One story, told the same way everywhere: the beta chain is retired, mainnet
starts now from a fresh genesis, and the disclosure is carved into block 0
itself.

The genesis coinbase message (permanent, verifiable by anyone):

> MoonBite 21/Sep/2026 beta chain retired every coin starts from zero

---

## X / Twitter thread

**1/**
MoonBite mainnet is live.

Money you can still mine on a laptop. RandomX proof-of-work, 2-minute
blocks, 10 MBITE per block, ~33M cap. No premine, no presale, no
allocation — block 0 pays nobody.

moonbite.org

**2/**
First, the honest part: everything before today was our public beta chain.
It's now retired, and every coin on it — including the founder's — is void.

We wrote that into the genesis block itself:
"MoonBite 21/Sep/2026 beta chain retired every coin starts from zero"

**3/**
Fair launch means the start line is the same for everyone. Nobody mined
before this announcement — you can check: block 0's timestamp message
names today's date, and the whole chain is public from its first block.

**4/**
Mining is one command. Download the miner, run it, and your laptop
competes on equal terms — RandomX is CPU-optimized and ASIC-resistant.

No pool. No signup. Every block you find pays you, and only you.

moonbite.org/mine

**5/**
Not an investment. Not a security. No price, no exchange listing, no
promises. Coins you mine today are worth the electricity you spent —
mine to own a piece of the network, not because you expect a payout.

Everything is open source. Don't trust us — verify.

---

## Site launch post (for /blog or the homepage banner)

**Mainnet is live. The beta chain is retired.**

Since August, MoonBite ran a public beta chain — real proof-of-work, real
software, real bugs found and fixed. That test period is over. The beta
chain is retired and every balance on it, the founder's included, is void.

Mainnet starts today from a fresh genesis block whose coinbase message
says exactly that, permanently:
"MoonBite 21/Sep/2026 beta chain retired every coin starts from zero"

From block 0, everyone mines under the same rules: 10 MBITE per 2-minute
block, halving every 1,650,000 blocks, ~33,000,000 MBITE cap, RandomX
CPU proof-of-work. No premine, no presale, no allocation.

Download the miner, run one command, and you're competing from the same
start line as everyone else — including us.

---

## Press-kit boilerplate patch

Replace the "Launch status" fast-fact with:

> Mainnet launched 21 September 2026 from a fresh genesis, following a
> public beta period whose chain was retired and voided. Testnet and
> regtest also run.

---

## Timing checklist (do in this order, announce LAST)

1. New binaries built (Linux + Windows) and verified on regtest.
2. Droplet seed wiped, new chain live, mining block 1+.
3. PC node + new wallet mining.
4. Miner bundles + SHA256SUMS republished, downloads verified fresh.
5. Site copy updated (genesis hash, launch date, beta-retired notices).
6. Explorer showing the new chain from block 0.
7. THEN post the thread. The announcement must never point at a network
   that isn't already fully up.
