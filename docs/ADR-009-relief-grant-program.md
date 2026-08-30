# ADR-009 — Relief-Grant Program (gifts of MBITE)

- **Status:** Proposed (dormant — activates only when ADR-008 preconditions are met)
- **Date:** 2026-07-22
- **Supersedes:** —
- **Superseded by:** —
- **Related:** ADR-006 (founder allocation / burn — the program is funded from
  disclosed, non-premine sources), ADR-008 (liquidity & merchant adoption — the
  precondition this ADR waits on).

## Context

The project wants to eventually direct some MBITE toward people in genuine need —
a "relief grant." The intent is charitable, but the design constraints are sharp,
and getting them wrong turns a good intention into either fraud, an unregistered
security, or unlicensed money transmission.

Three hard truths shape this decision:

1. **MBITE has no established value yet** (pre-mainnet, unlisted, zero trades).
   Granting a thing of undefined value is not charity — it is theatre, and it
   invites accusations of pumping a worthless token. Per ADR-008, value only
   becomes honest once liquidity **and** spend-utility exist. **This program stays
   dormant until then.**

2. **A grant must be an unconditional gift of MBITE — nothing else.** The moment
   the program takes fiat, pays someone's bills, converts MBITE to dollars, or
   holds funds on a recipient's behalf, it crosses the crypto↔fiat boundary and
   becomes **money transmission** (MSB licensing, KYC/AML). It also must not be a
   payment *for labor or services* (that reframes it as compensation/airdrop) nor
   carry any promise of future price appreciation (that risks looking like an
   investment contract / security). It is a gift. Full stop.

3. **Grants funded from a common pool need an honest, tamper-evident source and a
   transparent decision process**, or the program becomes a slush fund and a
   reputational liability for a project whose entire brand (ADR-006/007) is
   "every rule is fixed in code and public."

Four parameters were left open in earlier discussion and are decided here:
**eligibility**, **per-grant caps**, **pool size/source**, and **who approves**.

## Decision

Adopt a **dormant, opt-in, non-custodial relief-grant program** with the
following rules. It does **not** run until the ADR-008 preconditions are live.

### 0. Activation preconditions (all required)

- A functioning liquidity venue exists (ADR-008 order book has real, non-trivial
  two-sided activity, **or** MBITE is listed somewhere it can be exchanged).
- Real merchant spend-utility exists (ADR-008 directory has active merchants and
  at least some real on-chain invoice settlements).
- A published, auditable funding source exists (see §3).

Until every box is checked, the program is documentation only. No grants issue.

### 1. Nature of the grant

- Each grant is an **unconditional, one-way transfer of MBITE** to a recipient's
  **own** address. Non-custodial: the recipient controls the keys the moment it
  lands.
- **No fiat leg. No bill-pay. No conversion. No custody.** The program never holds
  a recipient's funds and never touches money.
- **No strings, no vesting, no clawback, no expectation of profit.** It is a gift,
  documented as such. The program makes **no** representation that MBITE will hold
  or gain value; recipients are told plainly it may be worth nothing.
- It is **not** compensation. Recipients are never asked to perform work, promote
  the project, refer others, or complete tasks in exchange. That would make it an
  airdrop-for-labor / compensation event, not relief.

### 2. Eligibility (default)

- **Self-attested need, lightweight.** An applicant submits their own MBITE
  address and a brief, honest statement of need. No fee to apply.
- **One active grant per person and per address.** Anti-Sybil is handled by the
  per-grant cap and pool rate-limits (§3), *not* by collecting sensitive identity
  documents — the program deliberately avoids becoming a KYC data honeypot, which
  is consistent with the project's pseudonymity posture.
- **Excluded:** the project's own maintainers, addresses associated with the
  funding source, and anyone using the grant as disguised compensation.
- Eligibility rules are published; changes ship as an amendment to this ADR.

### 3. Pool size & source (default)

- **Funded only from disclosed, non-premine MBITE.** Because ADR-006 burns founder
  allocation rather than holding it, the pool is **not** a premine slice. Permitted
  sources: voluntary donations to a published, watch-only program address, and/or
  a fixed, publicly announced allocation the community can verify on-chain. The
  source and every inflow/outflow are **publicly auditable on the chain**.
- **Fixed, announced pool per cycle** (e.g. per quarter). The program never spends
  beyond the announced cycle amount; when a cycle's pool is exhausted, grants pause
  until the next cycle. No borrowing against future cycles.
- The program address is **watch-only for observation**; actual disbursement keys
  are held by the approvers (§4), not by any server.

### 4. Approval (default)

- **Multisig, m-of-n, no single signer.** Disbursements require an **M-of-N
  multisig** (default **2-of-3**) so no one person can drain the pool. Signers are
  publicly named (by pseudonym) at activation.
- Every approved grant is **logged publicly** (grant id, amount, recipient address,
  date, and the on-chain txid) so the whole program is verifiable, matching the
  transparency standard of ADR-006/007.
- Denials require no justification beyond "cycle exhausted" or "failed the
  published eligibility rules"; the process is not adversarial.

### 5. Per-grant cap (default)

- A **small, fixed maximum per grant**, denominated in **MBITE** (not fiat — the
  program never references a dollar value, since doing so both implies a price and
  drifts toward money-transmission framing). The exact figure is set at activation
  relative to the then-current subsidy/emission, and published. Caps exist to make
  the pool reach more people and to blunt Sybil farming.

## Consequences

**Positive**

- The program can do genuine good *without* the project becoming a regulated money
  transmitter, a securities issuer, or a KYC data honeypot.
- Full on-chain auditability (funding source, multisig approvals, every grant txid)
  keeps it consistent with MoonBite's "fixed in code and public" brand.
- Dormancy-until-value prevents the worst failure mode: loudly gifting a
  valueless token and looking like a pump.

**Negative / accepted trade-offs**

- **The program does nothing for a while.** By design it waits on ADR-008. That is
  the honest cost of not overpromising.
- **Light-touch eligibility is Sybil-imperfect.** We accept some gaming as the
  price of not building an identity-document honeypot; caps + fixed pools bound the
  damage.
- **Self-attested need can be abused.** Mitigated, not eliminated, by public logs
  and small caps.
- **Multisig coordination is slower** than a single signer — accepted, because no
  single party should be able to move the pool.

## Alternatives considered

- **Run the program now, pre-value.** Rejected: grants of a valueless token are
  theatre and read as a pump (see ADR-008).
- **Pay recipients' bills / give fiat.** Rejected: money transmission (MSB), the
  exact boundary the project refuses to cross.
- **Condition grants on promotion, referrals, or tasks.** Rejected: that is
  compensation / an airdrop-for-labor, not relief, and muddies the gift framing.
- **Collect ID documents for eligibility.** Rejected: builds a KYC honeypot at odds
  with the project's pseudonymity and privacy posture; caps + public logs are the
  chosen anti-abuse tools instead.
- **Fund from a premine slice.** Rejected: contradicts ADR-006's no-premine burn;
  the pool must come from disclosed donations or a publicly verifiable allocation.
- **Single-signer treasury for speed.** Rejected: unacceptable custody/rug risk;
  multisig only.

## Notes

This ADR is intentionally **dormant**. Nothing in it should be presented publicly
as an active program or a promise. When (and only when) the ADR-008 preconditions
are met, activation means: publish the pool source and cycle amount, name the
multisig signers, publish the per-grant cap in MBITE, and open applications. Until
then it is a design record, not an offer.
