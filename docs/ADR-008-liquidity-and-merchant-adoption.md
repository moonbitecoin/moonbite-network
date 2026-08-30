# ADR-008 — Liquidity & Merchant Adoption (non-custodial)

- **Status:** Accepted
- **Date:** 2026-07-22
- **Supersedes:** —
- **Superseded by:** —
- **Related:** ADR-007 (no protocol revenue), ADR-006 (founder allocation / burn),
  ADR-007 (long-term sustainability — fees 100% to miner, governance freeze).
  A future **ADR-009** will cover the relief-grant program, which is
  intentionally deferred by this decision.

## Context

MoonBite (**MBITE**) is a RandomX PoW Litecoin-family chain. It is **pre-mainnet,
not listed on any exchange, and has recorded zero trades** — so it has **no
established market value**. A coin with no way to be traded and nowhere to be
spent has no reason for anyone to hold it, and no honest basis for any grant,
airdrop, or "relief" program: giving away a thing of undefined value is not a
gift, it's theatre.

Two things must exist *before* value is meaningful:

1. **Liquidity** — some venue where MBITE can be exchanged for another asset, so
   price discovery can begin.
2. **Utility** — somewhere MBITE can actually be *spent*, so holding it connects
   to real goods/services rather than pure speculation.

The hard constraint on *how* we provide these is regulatory. The moment our
software **holds customer funds, keys, or balances**, or touches the
**crypto↔fiat boundary** (taking money, paying bills, converting to dollars), it
becomes **money transmission** — an MSB activity requiring licensing and KYC/AML
in most jurisdictions. That is a line the project deliberately will not cross at
the software layer. See the pseudonymity/opsec posture in the project history for
why we avoid becoming a regulated intermediary.

Crypto-to-crypto, wallet-to-wallet, **non-custodial** software that never touches
customer funds is, by contrast, ordinary software. That is the only design space
we build in.

## Decision

Ship a **liquidity layer** and a **merchant-adoption layer**, both strictly
non-custodial. The server stores *intent and observation only*; it never holds
coins, keys, or balances, and never touches fiat.

### 1. Exchange — non-custodial order book (`exchange.py`)

- An **order-intent store** (SQLite) for the pairs **MBITE/LTC**, **MBITE/BTC**,
  and **MBITE/USDT**. Each order records the maker's side, price, amount, and the
  maker's own wallet addresses — *not* any funds.
- **Settlement is peer-to-peer via atomic swap (HTLC).** MBITE/LTC and MBITE/BTC
  are `native` — both legs live in the shared Bitcoin-script family, so an HTLC
  swap needs no third party. MBITE/USDT is flagged `contract` (the USDT leg needs
  a contract on its host chain) and is documented as harder.
- `settle_hint` performs the **hand-off**: when a taker wants an order, it returns
  both parties' swap addresses and the mechanism ("HTLC atomic swap,
  non-custodial") with **status `manual`** — the actual swap is executed by the
  two wallets, not the server. Full swap automation is explicitly **Phase 2** and
  out of scope here.
- The server **never matches, escrows, or settles**. It is a bulletin board with
  a price view. Makers can `cancel` their own orders (maker-only).

### 2. Merchants — "Accept MBITE" directory + invoices (`merchants.py`)

- A **merchant directory**: businesses that voluntarily list that they accept
  MBITE (name, category, URL, blurb, and their **own** receiving address). Capped
  at `MAX_MERCHANTS_PER_ADDRESS = 3` to limit spam.
- **Invoices** are non-custodial payment *requests*, not payment *processing*. The
  customer pays the merchant **directly, wallet-to-wallet**. We surface a
  BIP21-style URI (`moonbite:<address>?amount=<mbite>&label=<memo>`) the wallet
  prefills.
- **Payment detection is watch-only**, exactly how a watch-only wallet confirms a
  receipt: at invoice creation we snapshot `baseline = received_at_address(addr)`
  (sum of all outputs paying that address across the active chain — monotonic, so
  it never drops when the merchant later spends). The invoice flips **pending →
  paid** only when a *new* inbound amount `received_now - baseline >=
  amount_units` lands on-chain, and **pending → expired** past its TTL
  (default 1 hour). The server confirms a payment happened; it never receives one.
- Payment verification is **dependency-injected** (`received_lookup`) so the
  module is decoupled from any node: the demo wires it to the local educational
  node; production points it at the MoonBite node.

### 3. What we explicitly do NOT build

- **No custody, escrow, or hot wallet.** No server-held keys or balances, ever.
- **No fiat rails.** No bank/card handling, no "pay your bills in MBITE", no
  conversion to dollars — all of that is money transmission and is out.
- **No fabricated market data.** No prices, volumes, market caps, charts, invented
  exchange partnerships, or fake merchants. Until real trades exist there is no
  price to show, and the UI says so.
- **No relief grants yet** (deferred to ADR-009). A grant is a *gift of MBITE*,
  never bill-payment, and it is premature until the layers above give MBITE an
  honest, observable value.

## Consequences

**Positive**

- The project provides liquidity *primitives* and *utility* without becoming a
  regulated money transmitter. The software stays "just software."
- Users retain self-custody end-to-end; a server compromise cannot move funds
  because the server holds none.
- Honest by construction: with nothing to fabricate, the UI can only report what
  the chain actually shows (a pending invoice, a real received payment, an empty
  order book).

**Negative / accepted trade-offs**

- **Atomic-swap settlement is manual (Phase 2 pending).** `settle_hint` hands off
  addresses; the two wallets must complete the HTLC. This is deliberately
  un-automated for now.
- **Thin/empty markets at launch.** A non-custodial order book has no market maker
  and no seeded liquidity; the exchange listing checklist (`EXCHANGE_LISTING.md`)
  still describes the harder, separate path to real venues.
- **MBITE/USDT is second-class** until the contract leg is built.
- **Payment detection assumes an honest, deep chain.** On a young low-hash-power
  chain, confirmations matter; the demo verifies against the educational node and
  a production deployment must point `received_lookup` at a node with adequate
  confirmation depth.
- **Directory/invoice state is not consensus-critical** and lives in gitignored
  SQLite (`exchange.db`, `merchants.db`); it is disposable and must never be
  treated as a source of truth about funds.

## Alternatives considered

- **Custodial exchange / payment processor.** Rejected: triggers money-transmission
  licensing, KYC/AML, and custody risk — incompatible with the project's
  non-custodial and pseudonymity posture.
- **Fiat on/off ramp or bill-pay.** Rejected: crosses the crypto↔fiat boundary
  (MSB territory) by definition.
- **Fabricated "coming soon" prices / partner logos to look bigger.** Rejected on
  honesty grounds — no fabricated market data, full stop.
- **Launch a grant/relief program now to bootstrap holders.** Rejected as
  premature: with no liquidity or spend utility, MBITE has no honest value to
  grant. Revisit in ADR-009 once these layers are live.

## Notes

Reference implementation lives in this repository: `exchange.py`,
`merchants.py`, the `/api/exchange/*` and `/api/merchant*` routes in `web_app.py`,
and the `markets.html` / `merchants.html` UIs. The end-to-end merchant pay-flow
(create invoice → pay on-chain → watch-only detection flips it to *paid*) has been
verified against the local educational node.
