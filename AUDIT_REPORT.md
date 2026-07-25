# MoonBite (MBITE) — Security Audit Report

**Engagement:** MAX BOUNTY AUDITOR — private, in-house white-box assessment
**Target:** `moonbite.org` web layer (`web_app.py`, `exchange.py`, `merchants.py`, `swap_verifier.py`, `explorer/`)
**Method:** Static analysis + local PoC exploitation + invariant fuzzing. **No live-site interaction.**
**Out of scope (by owner):** C++ Litecoin consensus/crypto core; third-party dependency internals.
**Authorization:** Owner-confirmed ("I own moonbite.org and authorize testing").
**Date:** 2026-07-25

---

## 1. Executive summary

MoonBite's application layer is **well-built where it matters most**. Every economic
attack against the non-custodial exchange failed: the server holds no coins, no keys, and
no balances, so the classic "drain the exchange" class simply has no target. Price integrity
holds under a 4,000-step fuzz — a quoted price can only appear after a real, on-chain-verified
atomic swap. Classic web injection (SQLi, XSS, path traversal) is absent or neutralized, and
all secret comparisons are constant-time.

No **Critical** issues and **no path to user-fund loss** were found. The real weaknesses are
**infrastructure and plumbing**, not business logic. The single most important fix is a
**rate-limit bypass via a spoofable `X-Forwarded-For` header**, which lets one attacker
appear as unlimited distinct clients and defeat every per-client quota. The remainder are
medium/low hardening items: process-global wallet state shared across users, an unbounded
in-memory dict (slow memory-DoS), and missing HTTP security headers (notably HSTS) on a site
that will handle wallets.

**17 proof-of-concept / invariant tests were written and all pass**, doubling as a permanent
regression suite.

---

## 2. Severity dashboard

| Severity | Count | Items |
|---|---|---|
| 🔴 Critical | 0 | — |
| 🟠 High | 1 | XFF rate-limit bypass |
| 🟡 Medium | 3 | Global wallet state · unbounded memory · missing security headers |
| 🔵 Low | 2 | ecdsa Minerva CVE (not remotely reachable) · unauthenticated broadcast relay |
| ⚪ Informational | 1 | Exception strings surfaced in error JSON |
| ✅ Proven-safe | 7 | SQLi · XSS · path traversal · wash-trade · cancel-forgery · custody · SSRF |

**Test evidence:** `tests/security/` — 17 tests, 100% passing.

---

## 3. Findings

### FINDING #1 — Rate-limit bypass via spoofed `X-Forwarded-For`
- **Severity:** High
- **Class:** Broken anti-automation / access control (CWE-290, CWE-807)
- **Location:** `web_app.py:92` (`_client_id`), consumed by `rate_limit` at `web_app.py:100`
- **Description:** `_client_id()` returns the **leftmost** `X-Forwarded-For` hop. That value is
  fully attacker-controlled. Because the limiter keys on it, rotating the header makes one
  attacker look like an unlimited number of clients, so no per-client cap ever trips.
- **Impact:** Every rate-limited route (`/api/notify`, `/api/exchange/order`, `/api/wallet/new`,
  `/api/mining/start`, `/api/merchant/*`) can be flooded without limit — resource exhaustion,
  order-book spam, unbounded email capture, memory growth (see #2/#3).
- **Real-world caveat:** Fully exploitable only if nginx does **not** overwrite XFF. If the
  nginx config uses `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;` (appends),
  it is exploitable; `$remote_addr` (overwrites) mitigates it. **Pending owner's nginx block.**
- **PoC:** `tests/security/test_poc_web.py::test_xff_rotation_defeats_rate_limit` — 40 requests
  past a 10/60 cap with rotating XFF produce **zero** 429s; a fixed IP is throttled by call 11.
- **Fix:** Do not trust the client-supplied leftmost hop. Trust only the hop your own proxy
  appends (the **rightmost**), or fall back to `remote_addr`:
  ```python
  def _client_id() -> str:
      xff = request.headers.get("X-Forwarded-For", "")
      if xff:
          return xff.split(",")[-1].strip()   # the hop nginx itself appended
      return request.remote_addr or "unknown"
  ```
  And ensure nginx sets `proxy_set_header X-Forwarded-For $remote_addr;` (single trusted hop).
- **References:** CWE-290; OWASP "Identity Spoofing via X-Forwarded-For".

---

### FINDING #2 — Process-global wallet state shared across all users
- **Severity:** Medium
- **Class:** Improper isolation / information exposure (CWE-668)
- **Location:** `web_app.py:63` (`app.generated_addresses`), `web_app.py:702` (`/api/wallet/balance`)
- **Description:** Generated addresses live in one process-global dict. `/api/wallet/balance`
  sums UTXOs across **every** address in it, regardless of who generated them.
- **Impact:** One visitor's balance query reflects other visitors' addresses — cross-tenant
  information leak and incorrect balances. (Demo chain, so not fund loss, but a privacy/UX defect.)
- **PoC:** `tests/security/test_poc_web.py::test_wallet_balance_aggregates_across_all_users`.
- **Fix:** Scope generated addresses to a session (signed cookie) or return the address to the
  client and have `/balance` take an explicit address argument; never aggregate a global set.

---

### FINDING #3 — Unbounded in-memory growth (memory-DoS)
- **Severity:** Medium
- **Class:** Uncontrolled resource consumption (CWE-400)
- **Location:** `web_app.py:675` — `app.generated_addresses[pkh] = {...}` with no eviction
- **Description:** Every `/api/wallet/new` permanently adds an entry; nothing caps or expires it.
  Combined with #1, an attacker inflates it without limit.
- **Impact:** Slow memory exhaustion of the gunicorn worker → crash/restart.
- **PoC:** `tests/security/test_poc_web.py::test_wallet_new_grows_unbounded_memory` (200 calls → 200 entries).
- **Fix:** Bound it (e.g. `collections.OrderedDict` with a max size + LRU eviction, or a TTL),
  or drop server-side retention entirely and make the client hold its address.

---

### FINDING #4 — Missing HTTP security headers
- **Severity:** Medium
- **Class:** Security misconfiguration (CWE-693)
- **Location:** global response path (confirmed via live `curl -I` and local test client)
- **Description:** Responses carry no `Strict-Transport-Security`, `X-Content-Type-Options`,
  `X-Frame-Options`, or `Content-Security-Policy`. `Server:` also leaks `nginx/1.24.0 (Ubuntu)`.
- **Impact:** Missing **HSTS** allows SSL-strip downgrade on first visit — serious for a wallet
  site. No `X-Frame-Options`/CSP → clickjacking / injection surface.
- **PoC:** `tests/security/test_poc_web.py::test_no_security_headers_present`.
- **Fix (nginx preferred, covers static assets too):**
  ```nginx
  add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
  add_header X-Content-Type-Options "nosniff" always;
  add_header X-Frame-Options "DENY" always;
  add_header Content-Security-Policy "default-src 'self'; ..." always;
  server_tokens off;
  ```
  Or a Flask `@app.after_request` if you prefer app-level control.

---

### FINDING #5 — `ecdsa` Minerva timing vulnerability (PYSEC-2026-1325)
- **Severity:** Low (present in dependency; **not remotely reachable**)
- **Class:** Side-channel (CWE-208), CVSS 7.4 in isolation
- **Location:** `requirements.txt` / `requirements-web.txt` — `ecdsa==0.19.2`
- **Description:** python-ecdsa is vulnerable to a P-256 timing attack that can leak signing
  nonces. **However**, the web app never signs: `web_app.py:670` generates a keypair and
  **discards** the private key (returns only the public address). Signing (`transaction.py:162`,
  RFC-6979 deterministic) runs only in the Python demo node / CLI, and real production custody
  is the out-of-scope C++ node (libsecp256k1, constant-time). There is **no network-facing
  signing oracle** an attacker can time.
- **Impact:** None in the deployed threat model. Risk exists only if the Python demo/CLI is ever
  used to hold real value.
- **Fix:** No patch exists upstream (maintainer considers side-channels out of scope). Options:
  pin/document the risk; keep real custody on the C++ node; if the Python path ever handles real
  keys, migrate to `coincurve`/libsecp256k1.

---

### FINDING #6 — Unauthenticated transaction-broadcast relay
- **Severity:** Low
- **Class:** Missing rate limit / open relay (CWE-770)
- **Location:** `explorer/api.py:230` (`POST /tx/broadcast`) — Railway host
- **Description:** Anyone can submit raw transactions to the live node via the explorer, with no
  auth and no visible rate limit. This is intended explorer functionality, but unrated.
- **Impact:** Potential mempool spam / use of your node as a broadcast relay.
- **Fix:** Add a `@rate_limit` and consider a soft size/volume cap. (Node itself enforces
  consensus validity, so this is abuse-limiting, not a correctness fix.)

---

### FINDING #7 (Informational) — Internal exception strings in error responses
- **Severity:** Informational
- **Location:** multiple `except Exception as e: ... str(e)` handlers (e.g. `web_app.py:690`, `:840`)
- **Description:** Raw exception text is returned to clients, aiding fingerprinting.
- **Fix:** Log full detail server-side; return a generic message + error id.

---

## 4. Proven-safe (attacks attempted, defenses held)

| Attack | Evidence |
|---|---|
| SQL injection | Parameterized everywhere; dynamic `SET`/`IN` use frozenset-whitelisted columns only (bandit/semgrep + code review) |
| XSS | Jinja autoescape on; no `\|safe` on user input |
| Path traversal (`/downloads/..`) | `send_from_directory` rejects escapes — `test_poc_web.py::test_downloads_traversal_is_blocked` (5 payloads) |
| Wash-trade price fabrication | Orders match but never settle without the verifier — `test_poc_exchange` + 4,000-step fuzz |
| cancel_token forgery | Constant-time compare; address/order-id/truncated guesses all rejected |
| Settlement smuggling | Verifier column whitelist; illegal status rejected |
| Custody / solvency | Schema stores no private keys/seeds; server holds no funds (invariant I2) |
| Webhook SSRF | getaddrinfo + private-IP rejection before fetch |

---

## 5. Fix-priority checklist (hand to a dev)

- [ ] **P0 — Finding #1:** `_client_id` → trust rightmost XFF hop; set nginx `X-Forwarded-For $remote_addr`.
- [ ] **P1 — Finding #4:** add HSTS + `X-Content-Type-Options` + `X-Frame-Options` + CSP; `server_tokens off`.
- [ ] **P1 — Finding #2 & #3:** scope wallet addresses per-session (or client-held); bound/evict the dict.
- [ ] **P2 — Finding #6:** rate-limit `/tx/broadcast`.
- [ ] **P2 — Finding #7:** generic client errors + server-side logging.
- [ ] **P3 — Finding #5:** document ecdsa risk; keep real custody on C++ node.

---

## 6. Coverage — what was and was not tested

**Tested:** all Flask routes and inputs; exchange order/swap state machine; merchant invoicing;
rate limiter; downloads; auth (cancel_token, verifier token, webhook secret); SQL/template/path
sinks; dependency CVEs; price-integrity & non-custody invariants (fuzzed).

**NOT tested (gaps / by design):**
- **C++ consensus/PoW/crypto core** — out of scope by owner; recommend a dedicated Litecoin-fork review.
- **Live-site runtime** — no traffic sent to moonbite.org; XFF real-world severity depends on the
  nginx config (not yet provided).
- **nginx / OS / TLS config** — inferred from response headers only; no host access.
- **Railway node RPC surface** beyond static review of `explorer/`.
- **Frontend JS supply chain** — not enumerated.
- **Concurrency/race conditions** under real multi-worker gunicorn — single-process reasoning only
  (note: in-memory rate limiter is per-worker, so effective caps multiply by worker count).

---

## 7. Recommended follow-up

- **Fix P0/P1 items**, then re-run `tests/security/` (already wired as regression guards).
- **External review** of the C++ fork before mainnet value accrues (consensus is the crown jewel and was out of scope here).
- **Move rate limiting to a shared store** (Redis) so caps hold across gunicorn workers.
- **Ongoing bounty** once listed: Immunefi / Cantina / Code4rena.
- **Runtime monitoring:** alert on 4xx/5xx spikes, `/tx/broadcast` volume, worker memory (catches #1/#3 in the wild).
- **Incident response:** documented pause/disclose runbook ahead of exchange listing.

---

*17 PoC/invariant tests in `tests/security/` support this report. No Critical findings; no user-fund-loss path identified within the tested scope.*
