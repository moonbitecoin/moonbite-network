# MoonBite Launch Checklist

Living launch tracker. Update the status boxes as work lands. Companion docs:
`RUNBOOK.md` (VPS route), `railway-node/DEPLOY.md` (Railway route).

_Last updated: 2026-07-16_

---

## Launch readiness (RAG)

| Workstream | Status | Notes |
|---|---|---|
| Website | 🔴 Not live | `moonbite.org` A record → 192.64.117.55 (Namecheap Stellar) serves an unrelated parked site. Must repoint DNS → DO VPS and deploy `web_app` (see "moonbite.org hosting" below). |
| Deploy tooling (Railway kit) | 🟢 Done | `deploy/railway-node/` on `main` |
| Qt / client rebrand | 🟡 Amber | Committed in source; not yet in shipped binaries |
| Live seed node | 🔴 Red | No node exists yet |
| Chain liveness | 🔴 Red | Height 0 until a miner runs |

> **Perception risk:** the website is live, so visitors will assume the network
> is live. Closing the node/liveness gap is the critical path.

---

## Definition of Done — "MoonBite is live"

- [ ] Node reachable on public P2P 9444, block height increasing
- [ ] A second machine syncs from the seed (`bigcoin-cli addnode <ip>:9444 onetry`)
- [ ] Explorer serves real chain data (no demo banner)
- [ ] Website links to the live explorer

---

## Critical path (risk-first sequence)

Highest-uncertainty item is scheduled first: the node blocks everything else and
is the least-proven piece.

### 1. Node spike (timeboxed) — 🔴 not started
- [ ] Deploy `moonbite-node` on Railway (Root `/`, Dockerfile `deploy/railway-node/Dockerfile`)
- [ ] Attach Volume mounted at `/data`
- [ ] Set `BIGCOIN_RPC_USER`, `BIGCOIN_RPC_PASSWORD`, `MINE=1`
- [ ] Enable TCP Proxy on **9444 only**
- [ ] **Success gate:** deploy logs show height rising
- [ ] **Fail gate:** if the Railway container can't sustain it → pivot to VPS (`RUNBOOK.md`)

### 2. Explorer wiring — 🔴 blocked on #1
- [ ] Deploy `moonbite-explorer` (Root `explorer`)
- [ ] Vars: `BIGCOIN_RPC_HOST=moonbite-node.railway.internal`, port 9445, same creds
- [ ] Vars: `BIGCOIN_NAME=MoonBite`, `BIGCOIN_TICKER=MBITE`
- [ ] Generate public domain
- [ ] **Success gate:** real block/tx/search data, no demo banner

### 3. Network durability — 🔴 blocked on #1
- [ ] Stand up a **second** seed node (removes single point of failure)
- [ ] Confirm cross-node sync

### 4. Finalize (fast-follow, NOT critical path) — ⚪ deferred
- [ ] Bake seed(s) into `vSeeds`/`vFixedSeeds` (`src/chainparams.cpp`)
- [ ] Rebuild `moon1` binaries; refresh `release/SHA256SUMS`
- [ ] Add live explorer link to the website

---

## Risk register

| # | Risk | Prob | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| R1 | Railway node can't sustain P2P / CPU load | High | High | VPS is real home; Railway = bootstrap only | You |
| R2 | Volume not mounted → chain wiped on redeploy | Med | High | `/data` volume is step 1, not optional | You |
| R3 | RPC 9445 exposed publicly | Low | Critical | Only 9444 gets the TCP proxy | You |
| R4 | `big1` binary shows old address prefixes | High | Low | Cosmetic; rebuild `moon1` in step 4 | You |
| R5 | Single seed = single point of failure | High | Med | Add 2nd seed before public promotion (step 3) | You |

---

## Scope guardrail

Do **not** pull the `moon1` binary rebuild (step 4) into the launch critical
path. It is cosmetic (address-prefix display only) and network-compatible with
the shipped `big1` build. Bundling it in just delays a reachable network for no
functional gain — ship it as a fast-follow.

---

## moonbite.org hosting (marketing site / dashboard)

Target: serve `web_app:app` (Flask) from the DigitalOcean VPS behind nginx +
Let's Encrypt. The Railway service stays the **node/explorer**; only the
website moves here.

**Prerequisite — get the new code onto GitHub.** The deploy `git clone`s from
`moonbitecoin/MoonBite-Coin`. The local repo shares **no history** with
`origin/main` (9 remote commits vs 7 local, no merge-base), so a plain push is
rejected and force-push would destroy the remote. Reconcile deliberately (e.g.
graft local work onto a branch off `origin/main`, or open a fresh branch/PR).
**Never force-push `main`.** Until this lands, the VPS clone serves old code.

1. **DNS (Namecheap → Advanced DNS):** change the `@` A record for
   `moonbite.org` from `192.64.117.55` → **the DO droplet's public IP**; add a
   `www` A record to the same IP (or CNAME `www` → `moonbite.org`). Drop the
   Namecheap Stellar/parking records. TTL low (5 min) during cutover.
2. **Deploy the app (root on the VPS):**
   `curl -fsSL https://raw.githubusercontent.com/moonbitecoin/MoonBite-Coin/main/deploy/setup-dashboard.sh | bash`
   (installs venv from `requirements-web.txt`, gunicorn `web_app:app` on
   127.0.0.1:8050, nginx :80). Verify: `curl -sf http://127.0.0.1:8050/`.
3. **HTTPS (after DNS resolves to the VPS):**
   `DOMAIN=moonbite.org bash deploy/setup-https.sh` — issues a cert for both
   `moonbite.org` and `www.moonbite.org` and forces the HTTPS redirect.
4. **Verify live:** `https://moonbite.org/` shows the cinematic home;
   `/mine` offers the Reactor download; `/downloads/...zip` serves the real file.
