# MoonBite Threat Model

A forward-looking, adversarial review of the MoonBite stack (node, web dashboard,
deploy pipeline, mobile wallet, website/downloads, DNS/infra), organized by
attacker persona and projected across a ~10-year horizon.

This is a living document. Findings map to concrete code locations and carry a
**"bites"** timeline — when the risk realistically becomes exploitable. It is a
defensive artifact for MoonBite's own codebase; nothing here is an exploit recipe.

**Status legend:** `[ ]` open · `[~]` partially mitigated · `[x]` addressed

---

## Scope & assets

The things worth protecting, in order of severity if lost:

1. **User private keys / funds** — via the wallet and node binaries we distribute.
2. **Chain integrity** — the ledger itself (no double-spends, no deep reorgs).
3. **The distribution channel** — the website, downloads, and release binaries
   (compromise here = everyone's keys at once).
4. **Availability** — nodes, seeds, and the public dashboard staying up.
5. **Founder pseudonymity** — the opsec model MoonBite depends on.

---

## Update — parallel red-team run (2026-07-24)

All six personas were run together against the codebase. Two **new Criticals**
surfaced that the initial model missed, and the personas' findings chain into
concrete kill-chains.

### New Critical findings
- **[x] ECDSA random-nonce key leak** — `transaction.py` signed with `.sign()`
  (random `k`), not RFC 6979. Nonce reuse (low entropy, VM fork/snapshot, RNG
  bug) → private-key recovery from two signatures. **FIXED 2026-07-24**: now uses
  `sign_deterministic(..., hashfunc=sha256)` with matching verify; 152 tests pass.
- **[ ] Founder identity in git metadata** — commit `6f7bc27` carries the
  founder's real author email; `000b690` leaks the founder's old username. Both
  are reachable from HEAD and pushed to GitHub, so `git log --format='%ae'` on the
  public repo deanonymizes the founder. The content scrub missed commit metadata.
  (Identifiers intentionally not repeated here — see private opsec notes.)
  *Fix needs a history rewrite + force-push (sanctioned exception) + account
  rotation — owner action.*
- **[ ] Railway node RPC world-bindable with a live wallet** —
  `deploy/railway-node/entrypoint.sh:29-35` binds RPC to `0.0.0.0` +
  `rpcallowip=0.0.0.0/0` while `MINE=1` holds the funded `miner` wallet, and the
  password is passed on argv (readable via `/proc`). One exposed port = drained
  treasury. Contradicts the VPS config which correctly keeps RPC on `127.0.0.1`.

### Cross-cutting kill-chains (why the personas are worse together)
1. **One commit → mass key theft:** unprotected `main` → `curl|bash` deploys
   HEAD-of-`main` as root → unsigned wallet binaries in `/downloads` → every
   downloader's keys stolen. *Time-to-compromise: one merge.*
2. **Undetectable poisoned clone:** no registrar-lock/DNSSEC → domain repoint +
   auto-issued DV cert → checksum-next-to-binary with no signature → the site's
   own "verify with SHA256SUMS" advice gives false confidence.
3. **Drained treasury:** Railway RPC `0.0.0.0` + password-on-argv → `sendtoaddress`.
4. **Double-spend:** no checkpoints + single seed (eclipse) + rentable scrypt
   hashpower → reorg every exchange deposit.

### Additional confirmed findings (grounded in code)
- **Order-cancel & settle auth broken** — `exchange.py:170-183` trusts a MBITE
  address that's *published in the public book*; `settle_hint` leaks both maker
  addresses to anyone (`exchange.py:196-224`).
- **No consensus checkpoints; retarget manipulable** — unbounded reorg
  (`node.py` reorg on chainwork only), coarse 2× difficulty steps + loose 2 h
  future-time window enable time-warp/instamine; **1** live seed in
  `deploy/seeds.txt`.
- **CDN scripts without SRI** — `moonbite-site/index.html:325-328` load GSAP/
  lenis/split-type with no `integrity=`.
- **Leaked operational state tracked in git** — `CURRENT_TUNNEL_URL.txt`,
  `notify_signups.jsonl` should be `.gitignore`d, not committed.

---

## Persona 1 — "SmashPay": opportunistic web attacker  (bites: day one)

Targets the Flask dashboard (`web_app.py`) and its JSON APIs.

| # | Finding | Location | Impact |
|---|---------|----------|--------|
| 1.1 | **Broken authorization on order cancel** — auth is a plaintext MBITE address that is *published in the public order book*, so anyone can cancel anyone's order. | `web_app.py:272`, `exchange.py:170-183` | Griefing, market manipulation, price-discovery spoofing |
| 1.2 | **Wildcard CORS + no CSRF + state change over GET** — `Access-Control-Allow-Origin: *` on every response; `/api/mining/stop` is a GET. | `web_app.py:844-850`, `556` | Any site can drive the API from a victim's browser |
| 1.3 | **Unauthenticated content writes** — `add_merchant`/`create_invoice`/`notify` accept arbitrary `name`/`blurb`/`url`/`email` with no auth or rate limit. Classic HTML-XSS is blocked by client `esc()` (`merchants.html:182`), **but** there is no server-side URL-scheme allowlist, so a `javascript:`/`data:` `href` is possible, and the directory can be spammed / `notify_signups.jsonl` can be grown without bound. | `web_app.py:314,332,197`, `merchants.html:201-202` | Phishing links, directory poisoning, disk-fill DoS |
| 1.4 | **Mining DoS** — `/api/mining/start` has no upper bound on `blocks` and no rate limit; pegs the 512 MB droplet. | `web_app.py:491-494` | Single-request CPU exhaustion |
| 1.5 | **Latent Werkzeug debugger RCE** — `FLASK_DEBUG` defaults to `1` when run directly. Prod uses gunicorn (safe); one accidental `python web_app.py` on a public IP = interactive RCE console. | `web_app.py:866` | Full server takeover |

**Confirmed safe:** `exchange.py` uses parameterized SQL throughout — **no SQL
injection**. Email regex blocks newline log-injection. `send_from_directory`
resists path traversal. Client `esc()` blocks attribute-breakout / `<script>` XSS.

---

## Persona 2 — "GhostMiner": consensus / economics attacker  (bites: launch week → year 2) — *existential*

Where a small-cap **scrypt** chain actually dies.

- **2.1 Rented-hashpower 51% / deep reorg** — scrypt hashpower is a rentable
  commodity (NiceHash, idle Litecoin ASICs). A young chain with low total
  hashrate can be reorged for hours of rental cost → double-spend every exchange
  deposit. **Single most likely thing to kill MoonBite.**
- **2.2 Difficulty / time-warp / instamine** — Litecoin-fork retarget logic is
  manipulable via timestamps on a low-difficulty young chain.
- **2.3 Eclipse via the seed list** — `deploy/seeds.txt` bootstraps from
  essentially one Railway seed today; whoever controls a new node's first peers
  controls its view of the chain. Single seed = single eclipse point.

---

## Persona 3 — "SupplyChainSam": build / deploy attacker  (bites: continuous; worst-case catastrophic)

Attacks *how code and binaries reach users* — historically the #1 way crypto
projects lose everyone's funds at once.

- **3.1 `curl | bash` + auto-pull from `main`** — `setup-dashboard.sh` and the
  redeploy `git pull` `main` with no signature/tag pinning. Anyone who pushes to
  `main` (stolen GitHub creds, a bad merge) ships straight to the live droplet.
- **3.2 Unsigned release binaries** — `publish-node-binaries.sh` writes
  `SHA256SUMS.txt` *next to* the binary; swapping the binary swaps the checksum.
  No GPG/minisign = no real integrity → mass key theft via a trojaned wallet.
- **3.3 Unpinned dependencies** — `pip install flask gunicorn ecdsa` and pub.dev
  packages, no lockfile/hashes; one malicious version compromises every install.
- **3.4 The download endpoint is a bullseye** — `/downloads/<path>` serves the
  wallet + miner. A website compromise hands every visitor a trojaned wallet;
  the site's blast radius is *everyone's private keys*.

---

## Persona 4 — "KeyGrab": node-operator / RPC attacker  (bites: once 3rd-party nodes run)

- **4.1 RPC exposure** — `setup-node.sh` correctly generates random `mb_...`
  creds and keeps RPC on private 9445, but the moment an operator sets
  `rpcallowip=0.0.0.0/0` or opens the port, `sendtoaddress` = drained wallet.
- **4.2 Single-host root SSH** — the droplet runs as root over SSH with an
  unpatched kernel (`*** restart required ***`), no visible fail2ban/2FA; one
  host is both the public face and the wallet-download origin.
- **4.3 P2P memory / DoS** — the Railway node already OOM-crash-looped once;
  malformed-message and connection-exhaustion DoS against small nodes is easy.

---

## Persona 5 — "DomainRaider" / "SockPuppet": human-layer attacker  (bites: any time)

- **5.1 DNS / registrar hijack** — the waboom.net incident proved the fragility.
  Registrar-account takeover → repoint `moonbite.org` → pixel-perfect clone
  serving a poisoned wallet.
- **5.2 Pseudonymity break** — correlating commit timestamps, writing style,
  infra metadata, or one real-name leak deanonymizes the founder → coercion /
  legal pressure.
- **5.3 Fake-listing / airdrop phishing** — clone sites and "MBITE listed!" scams
  harvest keys as the coin gains recognition.

---

## Persona 6 — "Chronos": long-horizon / cryptographic attacker  (bites: year 5-10)

- **6.1 Quantum vs. ECDSA (secp256k1)** — `generate_keypair()` uses ECDSA; once a
  pubkey is revealed (reused/spent address), a future CRQC can forge signatures.
  Mitigation: never reuse addresses; plan a post-quantum signature migration.
- **6.2 Primitive aging** — scrypt/RIPEMD-160/SHA-256d are fine today; watch
  scrypt ASIC centralization rather than breakage.
- **6.3 Dependency & platform rot** — Flask/Werkzeug majors, abandoned pub.dev
  packages, Python EOL, OpenSSL CVEs. Unmaintained deps = slow-motion breach.
- **6.4 Regulatory drift** — `exchange.py` is deliberately non-custodial
  (`exchange.py:8-10`). Adding deposit/withdraw/fiat makes it a money
  transmitter — a legal "vulnerability" of the same severity as an RCE.

---

## Remediation ladder (highest ROI first)

### Tier 1 — Supply chain & distribution (protects everyone's keys)
- [ ] **Sign all releases** (GPG or minisign); publish the public key on the site,
      repo, and README — defeats 3.2 / 5.3.
- [ ] **Protect `main`**: required reviews, signed commits, no direct pushes — 3.1.
- [ ] **Deploy from signed tags**, not `main`; verify the tag signature in the
      deploy script before `git pull` — 3.1.
- [ ] **Pin dependencies**: `requirements-web.txt` with hashes; a committed pub.dev
      lockfile for the wallet — 3.3.
- [ ] **Serve downloads with published checksums *and* signatures on a separate
      origin** from the binary — 3.4.

### Tier 2 — Consensus honesty (keeps the ledger meaningful)
- [ ] Publish **minimum confirmation requirements** and enforce them in any listing
      guidance — 2.1.
- [ ] Ship **early developer checkpoints** to cap reorg depth on the young chain — 2.1 / 2.2.
- [ ] Keep the **"low hashrate = not final"** disclosure on `/why` and docs — 2.1.
- [ ] **Multiple independent seeds** in `deploy/seeds.txt`; document seed rotation — 2.3.

### Tier 3 — Web app hardening
- [ ] **Real maker auth on cancel**: prove control of the MBITE address by signing a
      server nonce, not by echoing the (public) address — 1.1.
- [ ] **Scope CORS** to the site origin; make every mutation a `POST` with a CSRF
      token; remove state-changing `GET`s — 1.2.
- [ ] **Server-side URL-scheme allowlist** (`http`/`https` only) on merchant `url`;
      rate-limit and cap all unauthenticated writes — 1.3.
- [ ] **Bound `blocks`** and rate-limit `/api/mining/start` — 1.4.
- [ ] **Force `FLASK_DEBUG=0`** by default; never expose the dev server — 1.5.

### Tier 4 — Infrastructure & operations
- [ ] **Rewrite git history** to purge the founder's real author email / old
      username from commit metadata (see 5.2); rotate linked accounts — new Critical.
- [ ] **Un-track leaked operational state**: `git rm --cached`
      `CURRENT_TUNNEL_URL.txt` + `notify_signups.jsonl`, then `.gitignore` them.
- [ ] **Stop binding Railway RPC to `0.0.0.0`**; scope `rpcallowip`, move the
      password off argv (`rpcauth`/cookie), don't co-locate the funded wallet — new Critical (4.1).
- [ ] **Add SRI + pin/self-host CDN scripts** in `moonbite-site/index.html` — 3.x.
- [ ] **Registrar lock + 2FA + DNSSEC** on moonbite.org — 5.1.
- [ ] **Non-root deploy user**, SSH key-only + fail2ban, **patch the kernel** — 4.2.
- [ ] **Never expose RPC**: enforce `rpcbind=127.0.0.1` / tight `rpcallowip`,
      document the risk loudly in `setup-node.sh` — 4.1.
- [ ] **P2P resource caps** and OOM guards on seed nodes — 4.3.

### Tier 5 — Long horizon
- [x] **Deterministic ECDSA nonces (RFC 6979)** in `transaction.py` — done 2026-07-24.
- [ ] **Address-reuse avoidance** guidance in the wallet now — 6.1.
- [ ] **Post-quantum signature migration** as a long-roadmap item — 6.1.
- [ ] **Dependency freshness** CI check (flag EOL/abandoned deps) — 6.3.
- [ ] **Keep custody boundaries**: no deposit/withdraw/fiat in `exchange.py` — 6.4.

---

## Confirmed-safe (audited, no change needed)

- Parameterized SQL in `exchange.py` — no SQLi.
- `send_from_directory` in `/downloads` — no path traversal.
- Email regex rejects control chars — no log injection via `/api/notify`.
- Client `esc()` blocks HTML/attribute-breakout XSS in the merchant list.
- The internal exchange is genuinely non-custodial (matchmaking only).
