# moonbite.org — Home Page Design & Copy Deck

Authoritative inputs: `docs/moonbite-guidelines.html` (brand), `web_app.py::_consensus_dict`
(consensus), live node at `/api/blockchain/info`. Figures below are real unless wrapped in
`{BRACES}`, which are live-bound placeholders with their source named.

**Verified constants** — RandomX proof of work · 120 s target block · 10 MBITE subsidy ·
halving every 1,650,000 blocks (~6.27 y) · ~33,000,000 cap · retarget every 60 blocks ·
coinbase matures 100 blocks · mainnet opened 3 September 2026 · final block ≈ 2214 ·
bech32 addresses (`moon1…`) · P2P 9444.

---

## A. Page strategy

The visitor should leave believing one thing: **MBITE cannot be given to anyone, only found —
and that constraint is enforced by code they can read, not by a promise anyone made.** The
emotional arc runs suspicion → curiosity → recognition → agency. A stranger arrives assuming
this is another coin someone is trying to sell them, so the page opens by removing the seller
entirely, which is disarming rather than persuasive. Curiosity takes over once they realise
the coins had to come from somewhere, and the page answers that with mechanism instead of
adjectives. Recognition lands when the live chain ticks in front of them and the thing stops
being a pitch and becomes a machine that is already running. Agency closes it: the only way in
is to do the work, and the work is four minutes of setup on hardware they already own. Nowhere
does the page argue that MBITE is valuable — it argues that MBITE is *honest*, and lets the
reader draw the harder conclusion themselves.

---

## B. Section-by-section blueprint

### 1 — Hero

- **Purpose.** Remove the seller. A first-time reader's defence against every crypto page is
  "someone is trying to take my money"; the fastest way through it is to be the page that has
  nothing to take.
- **Headline.** Nobody was handed a single coin.
- **Supporting copy.** Not the people who wrote MoonBite, not an investor, not a fund. When the
  network opened, the supply was zero. It has grown by exactly one route since.
- **Open loop.** If nobody was given any — where did the {SUPPLY_MINED} in existence come from?
- **Technical layer** (sub-line, always visible, monospace figures): `No premine · no presale ·
  no allocation · RandomX · 120 s target · 10 MBITE per block · cap ~33,000,000`
- **Layout.** Full viewport, dark. Mark sits alone above the headline at 96 px. Headline is the
  page's single largest statement — one of only two permitted uses of display type. Copy column
  capped at 34 ch so the line breaks are deliberate. Two actions: `Start mining` (gold, the one
  primary action on the screen) and `Verify this yourself` (ghost, jumps to §2).
- **Signature interaction.** The bitten moon is bound to the live chain: **each time a block is
  found, the bite deepens by one increment, then eases back.** This is the motion the brand
  standard already reserves as the mined-block signature. It fires on real data from
  `/api/blockchain/info`, so the mark on the page is a status light, not a loop.

### 2 — The fair-launch proof

- **Purpose.** Convert the hero's claim from assertion into something checkable in one click.
- **Headline.** Every coin can be traced back to the work that made it.
- **Supporting copy.** There is no ledger entry that came from anywhere except a solved block.
  You do not have to believe that. The chain is public, the genesis block is the first thing in
  it, and it paid out nothing to anyone.
- **Open loop.** So what exactly does "solving a block" cost?
- **Technical layer.** Genesis hash `{GENESIS_HASH}` (source: `/api/consensus`, field to be
  added — see §E gap 1). Inline, copyable verification:
  ```
  moonbite-cli getblockhash 0
  moonbite-cli getblock <hash> 2      # coinbase outputs: none held back
  moonbite-cli gettxoutsetinfo        # total_amount == blocks × subsidy
  ```
  Plus a one-line identity: total issued should equal blocks mined × subsidy, and the page shows
  both numbers side by side so the arithmetic is visible: {BLOCK_HEIGHT} × 10 = {SUPPLY_MINED}.
- **Layout.** Two columns. Left: the plain claim in body type. Right: a terminal block in
  monospace with a copy button. Hairline rule above and below; no card, no shadow.
- **Interaction.** The equation resolves live — as a block lands, both numbers increment together
  and the `=` flashes once. Watching the identity hold is the proof.

### 3 — How mining works

- **Purpose.** Turn an abstract word into three concrete things a laptop does.
- **Headline.** What your computer is actually doing.
- **Supporting copy.** It is not "generating" coins, and it is not solving anything useful to
  anyone else. It is guessing, very fast, at a number that is hard to find and trivial to check.
- **Open loop.** Why would anyone design money that has to be expensive to make?
- **Steps** (plain layer / technical layer beneath each):
  1. **It collects the transactions nobody has written down yet.** — Mempool assembly; your node
     validates each one against consensus rules before it will include it.
  2. **It guesses until a guess is small enough.** — RandomX hashes the block header against the
     target implied by `bits`; current difficulty {DIFFICULTY}, retargeting every 60 blocks
     toward the 120 s interval.
  3. **When it wins, everyone else checks the work in a millisecond.** — Asymmetry is the whole
     point: expensive to produce, cheap to verify. The subsidy is spendable after 100 blocks.
- **Layout.** Three steps on a horizontal rail, numbered in monospace gold. Each step's technical
  layer sits in a `<details>` that is open by default on desktop and collapsed on mobile — the
  layering rule solved without hiding anything from an engineer.
- **Interaction.** A live guess counter runs beneath step 2 while the section is on screen,
  showing hashes attempted by the visitor's own browser against a toy target — no coins, clearly
  labelled as a demonstration, and it stops when scrolled past. It makes "guessing very fast"
  physical without pretending to mine.

### 4 — Why proof of work in 2026

- **Purpose.** Meet the strongest objection head on rather than waiting for the FAQ.
- **Headline.** Money that is cheap to make is money somebody will make.
- **Supporting copy.** Every alternative eventually asks you to trust whoever holds the most of
  it, or whoever wrote the list of who may vote. Work is the only entry cost that cannot be
  granted to a friend.
- **Open loop.** Then why does MoonBite refuse the hardware everyone else mines with?
- **Technical layer.** RandomX is chosen deliberately over SHA-256: it is memory-hard and tuned
  for general-purpose CPUs, so the advantage of purpose-built hardware is small enough that a
  desk machine stays viable. Stated plainly and without overclaiming: ASIC resistance is a
  moving target, not a permanent property, and MoonBite treats it as something to defend rather
  than something achieved.
- **Energy, said out loud.** Proof of work costs electricity. That is the mechanism, not a side
  effect. The page states it in the affirmative rather than burying it — a Bitcoin Core reader
  will respect the admission and a lawyer will find nothing to flag.
- **Layout.** Single centred column, generous leading, no illustration. The one section on the
  page that is pure argument, so it is set as an essay, not a card grid.
- **Interaction.** None. Deliberate stillness after the motion of §3 — the page should feel like
  it lowers its voice here.

### 5 — Live network state

- **Purpose.** Stop the page being a brochure. Something is happening whether or not you read on.
- **Headline.** It is running right now, whether or not you are watching.
- **Supporting copy.** Nothing here is a mock-up. These are the numbers this page asked the
  network for when you opened it.
- **Open loop.** How much of it is already gone?
- **Metrics** (all monospace, tabular figures, per the type standard):
  | Reading | Placeholder | Source |
  |---|---|---|
  | Block height | `{BLOCK_HEIGHT}` | `/api/blockchain/info` → `height` |
  | Chain tip | `{TIP_HASH}` | `/api/blockchain/info` → `tip_hash` |
  | Difficulty | `{DIFFICULTY}` | `/api/blockchain/info` → `difficulty` |
  | Total issued | `{SUPPLY_MINED}` | `/api/blockchain/info` → `total_money_coins` |
  | Network hashrate | `{HASHRATE}` | needs `getnetworkhashps` — see §E gap 2 |
  | Reachable nodes | `{NODE_COUNT}` | needs a crawler — see §E gap 3 |
  | Last block seen | `{SECONDS_AGO}` | derived from `median_time` |
- **Layout.** A single hairline-ruled instrument rail, not cards. Values large, labels small
  above them in caps under 20 characters (the only place all-caps is permitted).
- **Interaction.** The mark's bite deepens here too, synchronised with the hero. If a block has
  not arrived in over 10 minutes the rail says so plainly rather than showing a stale number —
  honesty at the moment it costs something is the most persuasive thing on the page.

### 6 — Supply, drawn as a shape

- **Purpose.** Make scarcity felt spatially instead of read as a table.
- **Headline.** The reward only ever falls.
- **Supporting copy.** Ten becomes five, five becomes two and a half, and the arithmetic runs out
  before the next century does. No vote can raise it, because raising it would produce a chain
  every existing node rejects.
- **Open loop.** If it all ends, what keeps the network alive afterwards?
- **The shape.** A descending staircase across the full width: each tread is one 1,650,000-block
  era, each riser a halving, the area beneath filled to show issuance. The already-mined portion
  is a thin gold sliver at the extreme left — at {BLOCK_HEIGHT} of 1,650,000 blocks the first
  era is barely begun, and the visual should be honest about how small that sliver is rather
  than exaggerating it for drama.
- **Technical layer.** Beneath the shape: subsidy `10 → 5 → 2.5 …`, halving interval 1,650,000
  blocks (~6.27 years), cap ~33,000,000 MBITE, last subsidy ≈ 2214, and the plain statement that
  the tail is fee-funded thereafter and that this is an unsolved economic question for every
  fixed-cap chain, MoonBite included (see ADR-011).
- **Interaction.** Hovering any tread reads out that era's dates, subsidy and cumulative supply.
  On touch it steps with a swipe. The current era is marked with a single gold tick that sits
  where the network actually is.

### 7 — Security and code

- **Purpose.** Give a hostile engineer the fastest possible route to the part that matters.
- **Headline.** The part that decides is small enough to read.
- **Supporting copy.** Most of this codebase is not ours and should not be. The consensus changes
  are few, listed here, and each one links to the line that implements it.
- **Open loop.** What has actually shipped, and what is still missing?
- **Technical layer — stated without spin.**
  - MoonBite Core is a **fork of Litecoin Core**, which is itself a fork of Bitcoin Core. This is
    disclosed in the first sentence, not discovered by the reader. The inherited code carries
    over a decade of review; the delta is what deserves scrutiny.
  - Enumerated consensus delta: RandomX proof of work in place of scrypt; 120 s target;
    10 MBITE subsidy; 1,650,000-block halving; 60-block retarget; bech32 HRP `moon`;
    P2P 9444. Each row links to the commit and file.
  - Repositories: `github.com/moonbitecoin/moonbite-core` (node),
    `github.com/moonbitecoin/MoonBite-Coin` (this site).
  - Wallet derivation: BIP39 mnemonic → BIP84 `m/84'/2'/0'/0/0` → P2WPKH.
  - **Audit status: none.** No paid third-party audit has been commissioned. Saying so is worth
    more than any badge, and the alternative is a claim that cannot survive a single question.
  - Governance decisions live as numbered ADRs at `/governance`, including the founder-mining
    disclosure (ADR-006) and the locked emission schedule (ADR-011).
- **Layout.** A table that is allowed to look like a table — engineers want density here, not
  air. Monospace throughout, each row a link.
- **Interaction.** One button: `Diff against Litecoin Core`, opening the compare view. The most
  aggressive trust gesture on the page is handing a sceptic the exact tool they would have used
  to attack you.

### 8 — Roadmap, as commitments already met

- **Purpose.** Roadmaps are where credibility is usually spent; this one spends it in reverse by
  leading with what already runs.
- **Headline.** Shipped, then not yet shipped.
- **Supporting copy.** The top half is verifiable this minute. The bottom half is not, and is
  written without dates for that reason.
- **Open loop.** How do you hold any of this?
- **Shipped** (each with a verify link): mainnet open since 3 September 2026 · RandomX consensus ·
  self-custody wallet with 12-word recovery · block explorer · public node software and build
  instructions · published consensus parameters at `/api/consensus`.
- **Not yet shipped, and honest about it:** additional seed nodes and a published node count ·
  third-party audit · reproducible builds · exchange listings, which are not in our gift and are
  not promised anywhere on this site.
- **Layout.** Two stacked lists, the shipped list in Bone, the pending list in Ash at the same
  size — deliberately not greyed into invisibility.
- **Interaction.** Every shipped row expands to the evidence: a command, a link or a hash.

### 9 — Holding and getting MBITE

- **Purpose.** Convert, and set expectations that protect the reader.
- **Headline.** Twelve words are the whole account.
- **Supporting copy.** There is no login, no recovery email and no support desk that can move your
  coins, which is the same sentence read from both directions. Write the words on paper.
- **Open loop.** What is stopping you starting tonight?
- **Technical layer.** BIP39 12-word mnemonic, BIP84 derivation, P2WPKH `moon1…` addresses,
  coinbase spendable after 100 blocks, MWEB available for optional confidential transfers.
- **The honest paragraph.** MBITE is not listed on any exchange, has no market price, and may
  never have one. Nobody can sell it to you today, and anyone who offers to is lying. This block
  is a scam-prevention control as much as a disclosure.
- **Layout.** Two doors, equal weight: `Download the wallet` and `Start mining`. No third option,
  because there is no third way to obtain a coin.
- **Interaction.** The wallet download detects the visitor's platform and names the file and its
  size before they click.

### 10 — Objections

- **Purpose.** Answer what a sceptic is actually thinking, in their words.
- **Headline.** The questions worth asking.
- Format: plain question, direct first sentence, technical detail after. No question exists to
  set up a boast.
  - **Is this a scam?** — The usual mechanism of a crypto scam is selling you something. There is
    nothing here to buy. Judge us on the absence of a sale, then on the code.
  - **Why mine something with no price?** — Because there is no way to acquire it later that does
    not depend on someone choosing to sell. If it never has a price, you spent some electricity
    on a curiosity. That is the honest range of outcomes.
  - **Who is behind it?** — The contributors are anonymous by choice, which is a cost as well as a
    principle: you get code you can audit instead of names you would have to trust. Founder
    mining is disclosed in ADR-006.
  - **Isn't this just a Litecoin copy?** — In large part, yes, and deliberately: consensus code is
    the worst place to be original. §7 lists everything that differs.
  - **What if you disappear?** — The network does not need this website. Node software, seeds and
    build instructions are public; the chain continues as long as anyone mines it.
  - **Will it be listed on an exchange?** — Unknown, and not promised. Listings are decided by
    exchanges, not by us.
- **Layout.** Accordion, one open at a time, questions in body weight — not styled to look
  reassuring.

### 11 — Footer

Mark, one line of orientation (`Fair-launch proof-of-work money. 10 MBITE every two minutes, to
whoever does the work.`), and four columns: Start, Verify, Understand, Governance. Closing rule
carries the network's live tip hash — the last thing on the page is a fact, not a slogan.

---

## C. Copy deck — final wording

> **Hero**
> FAIR LAUNCH · PROOF OF WORK
> # Nobody was handed a single coin.
> Not the people who wrote MoonBite, not an investor, not a fund. When the network opened, the
> supply was zero. It has grown by exactly one route since.
> `No premine · no presale · no allocation · RandomX · 120 s block · 10 MBITE · cap ~33,000,000`
> [ Start mining ] [ Verify this yourself ]

> **Proof**
> ## Every coin can be traced back to the work that made it.
> There is no entry in this ledger that came from anywhere but a solved block. You do not have to
> take that on faith — the chain is public, the genesis block is the first thing in it, and it
> paid out nothing to anyone.
> {BLOCK_HEIGHT} blocks × 10 MBITE = {SUPPLY_MINED} MBITE. The identity holds, block after block.

> **Mining**
> ## What your computer is actually doing.
> It is not "generating" coins and it is not solving anything useful to anyone else. It is
> guessing, very fast, at a number that is hard to find and trivial to check.
> **It collects the transactions nobody has written down yet.**
> **It guesses until a guess is small enough.**
> **When it wins, everyone else checks the work in a millisecond.**

> **Why work**
> ## Money that is cheap to make is money somebody will make.
> Every alternative eventually asks you to trust whoever holds the most of it, or whoever wrote
> the list of who may vote. Work is the only entry cost that cannot be granted to a friend.
> This costs electricity. That is the mechanism, not a footnote — a coin that costs nothing to
> create is worth exactly what it cost.

> **Live**
> ## It is running right now, whether or not you are watching.
> Nothing here is a mock-up. These are the numbers this page asked the network for when you
> opened it.

> **Supply**
> ## The reward only ever falls.
> Ten becomes five, five becomes two and a half, and the arithmetic runs out before the next
> century does. No vote can raise it, because a chain that raised it is a chain every existing
> node rejects.

> **Code**
> ## The part that decides is small enough to read.
> Most of this codebase is not ours, and should not be. MoonBite Core is a fork of Litecoin Core,
> which is a fork of Bitcoin Core. The consensus changes are few, listed below, and each links to
> the line that implements it. No third-party audit has been commissioned; we would rather write
> that than a sentence we cannot defend.

> **Roadmap**
> ## Shipped, then not yet shipped.
> The top half is verifiable this minute. The bottom half is not, and carries no dates for that
> reason.

> **Wallet**
> ## Twelve words are the whole account.
> No login, no recovery email, and no support desk that can move your coins — which is the same
> sentence read from both directions. Write the words down on paper before you mine anything.
> MBITE is not listed on any exchange and has no market price. Nobody can sell it to you today,
> and anyone offering to is lying.

> **Objections**
> ## The questions worth asking.

> **Footer**
> Fair-launch proof-of-work money. 10 MBITE every two minutes, to whoever does the work.

---

## D. Visual system notes

- **Hierarchy.** Display type (Archivo Black) appears exactly twice: the wordmark and the hero
  line, per the type standard. Every other heading is Inter 700/800. Body Inter 400/16 px/1.6.
  Every figure that is money, a hash, an address or a height is monospace with tabular figures,
  so nothing shifts width as it updates.
- **Case.** Sentence case throughout. All-caps only for eyebrows and labels under 20 characters.
- **Colour.** Void `#0B0D12` ground, Bone `#F5F2EA` text, Ash `#8A8580` secondary, Moongold
  `#D9A441` reserved for exactly one primary action per screen plus data emphasis. Red and green
  are functional only — never decorative, never for sentiment.
- **Dark by default.** The page has one appearance. It is not theme-switched, and colour tokens
  are declared once rather than per-media-query.
- **Motion.** One curve, `cubic-bezier(0.22, 1, 0.36, 1)`; three durations — 120 ms feedback,
  240 ms transition, 600 ms narrative. **One signature animation: the bite deepens by an
  increment when a block is found**, bound to live chain data, used in the hero and the live rail
  and nowhere else. Everything else is opacity and 8–16 px of travel. Under
  `prefers-reduced-motion` the bite becomes a static counter, as the motion standard requires.
- **Grid.** 12 columns, 1180 px max, 24 px gutters, 8 px spacing base. Text measure never exceeds
  68 ch. Breakpoints 480 / 768 / 1024 / 1280; the instrument rail and the staircase are the two
  elements permitted to scroll horizontally inside their own container.
- **Iconography.** 24 px grid, 2 px stroke, round caps, geometric construction only, Ash or Bone —
  gold is not available to icons, only to the primary action.
- **Imagery.** No rendered 3D coins, no rockets, no astronauts. Where imagery is used it is
  photographic hardware and real night, duotoned into Void and Bone. *(Note: this rules out the
  shaded cratered sphere used in the `/film` prototype — see the open question in §E.)*
- **Accessibility (WCAG AA).** Body Bone-on-Void ≈ 15:1; Ash-on-Void ≈ 5.3:1 — Ash is therefore
  permitted for body but never below 16 px; gold-on-Void ≈ 8.2:1. Gold is never used as a text
  colour on white. All live regions are `aria-live="polite"` so a screen reader is told the
  height changed without being interrupted every two minutes. Every `<details>` is keyboard
  reachable, focus rings are never removed, the accordion is a real button set, and the hash-rate
  demo has a visible pause control.

---

## E. Trust checklist — verifiable in one click

| Claim on the page | How a sceptic checks it | Status |
|---|---|---|
| No premine | Genesis block coinbase, shown and linked to the explorer | ✅ available |
| Supply is what we say | `{BLOCK_HEIGHT} × 10 = {SUPPLY_MINED}`, both live from the node | ✅ available |
| Consensus rules are real | `/api/consensus` returned verbatim, plus the code line for each | ✅ available |
| The chain is live | Tip hash and block age, refreshed on load | ✅ available |
| Code is public | Repo links; `Diff against Litecoin Core` compare view | ✅ available |
| It is a Litecoin fork | Stated by us in §7 before anyone finds it | ✅ available |
| Founder mining | ADR-006 at `/governance` | ✅ available |
| Emission cannot change | ADR-011, plus the node rule that rejects a richer chain | ✅ available |
| Wallet is self-custody | BIP39/BIP84 paths published; derive the address offline and compare | ✅ available |
| No audit exists | Said plainly rather than implied | ✅ available |

**Gaps to close before launch — these must not be faked:**

1. **`{GENESIS_HASH}` is not currently exposed.** Add it to `_consensus_dict` (`getblockhash 0`)
   rather than hard-coding it into the template.
2. **`{HASHRATE}` has no endpoint.** Surface `getnetworkhashps` through the API. Until it exists,
   omit the metric — do not estimate it.
3. **`{NODE_COUNT}` cannot be honestly shown yet.** The droplet is presently the only published
   seed, so any count would flatter. Either ship a crawler or replace the metric with the seed
   list, which is true and less impressive.
4. **`/api/consensus` reports `height: 0`** because it still reads the retired Python chain while
   `/api/blockchain/info` correctly reports the node. Bind every height on the page to the
   latter, and fix the former.

---

## F. Three hero directions to test

**Direction 1 — Removal.** *Confident, disarming, best against a suspicious cold audience.*
> # Nobody was handed a single coin.
> Not the people who wrote MoonBite, not an investor, not a fund. When the network opened, the
> supply was zero.

**Direction 2 — Mechanism.** *Concrete and physical; strongest with technical readers and the
one most likely to be screenshotted by an engineer.*
> # Ten coins appear every two minutes, and no one decides who gets them.
> A number is found or it is not. The machine that finds it is paid, and nothing else in the
> system has an opinion.

**Direction 3 — Time.** *Narrative and urgent without a price claim; the highest-risk, highest-
ceiling option.*
> # This is the cheapest MoonBite will ever be to make.
> Difficulty rises as machines arrive and the subsidy halves on a fixed schedule. The arithmetic
> only moves one way, and it has already started.

> ⚠️ Direction 3 wins attention but flirts with an investment implication. If tested, it must run
> with the "no price, may never have one" line **inside the hero**, not below the fold.

---

## Quality-bar audit

**Retail visitor, 30 seconds.** First draft opened on the fork disclosure and lost them
immediately — a newcomer does not know what Litecoin is, so it read as an admission of something
bad. Moved to §7 where it reads as candour to the only audience that cares. Also cut every
instance of "hash", "UTXO" and "consensus" from the headline layer; they now appear only beneath
a plain-language line. **Verdict: stays.**

**Bitcoin Core contributor, looking for a reason to dismiss.** Two changes forced. First, an
earlier line called RandomX "ASIC-proof", which is false; it now says resistance is defended, not
achieved. Second, an "energy-efficient" claim was removed entirely and replaced with a direct
statement that proof of work costs electricity — the section is stronger for conceding it. The
`Diff against Litecoin Core` button was added specifically because this reader will do that
comparison anyway, and doing it for them converts the strongest attack into the strongest signal.
**Verdict: no longer trivially dismissible.**

**Securities lawyer.** Removed a "get in early" framing from Direction 3's body and flagged the
direction itself. No price, return, appreciation or expectation-of-profit language survives
anywhere. The wallet section now carries an affirmative no-market-price statement rather than
leaving it to inference, and no roadmap item carries a date that could be read as a promise.
The one residual risk is Direction 3's headline, which is annotated rather than silently shipped.
**Verdict: clean, with that single flag.**
