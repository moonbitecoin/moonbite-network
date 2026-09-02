> **Retired (2026-09-03).** The Railway seed was dropped; the DigitalOcean droplet
> (`deploy/seeds.txt`) is the network's seed. Kept for reference only.

# Deploy MoonBite live on Railway (node + explorer)

This directory ships the **MoonBite seed node** as a Docker service for Railway,
and pairs it with the Flask **explorer** in `explorer/`. Follow the two steps in
order — the explorer needs the node to exist first.

> **Honest launch notes — read once before deploying**
> - **A fresh chain produces NO blocks on its own.** With zero miners the height
>   stays at 0 forever. Set `MINE=1` on the node service (below) so it mines, or
>   run the miner yourself. Railway containers are small, so expect slow block
>   production.
> - **RPC port 9445 must stay private.** Only attach a public domain / TCP proxy
>   to the **P2P port 9444**. The explorer reaches RPC over Railway's *private*
>   network (`*.railway.internal`). Never expose 9445 publicly.
> - **Persistence:** attach a Railway **Volume** mounted at `/data`, or the chain
>   is wiped on every redeploy.
> - **Binary identity:** the shipped `release/bin/moonbited` must be the ADR-010
>   build (2-minute blocks, subsidy 10 MBITE, halving 1,650,000, 60-block retarget;
>   genesis hashes re-mined at re-genesis). A node still running the older
>   10-minute / 50 MBITE build is on a different chain and will not sync.
> - **Railway is not the ideal home for a P2P node** (built for HTTP). A small
>   $4–6/mo VPS is more robust for a long-lived seed. This Docker path works as a
>   bootstrap seed; see `deploy/RUNBOOK.md` for the VPS route.

---

## Step 1 — Node service (Docker)

**Prompt to paste into your Railway browser session:**

> Deploy a service on Railway from the GitHub repo **moonbitecoin/MoonBite-Coin**.
> - New Project → "Deploy from GitHub repo" → select `moonbitecoin/MoonBite-Coin`.
> - Name the service **moonbite-node**.
> - In **Settings → Build**: set **Root Directory** to `/` (repo root) and
>   **Dockerfile Path** to `deploy/railway-node/Dockerfile.node`
>   (the build context must be the repo root so it can COPY `release/bin/moonbited`).
>   **Not** `Dockerfile` — that path builds the Flask web app, not the daemon.
> - Add a **Volume** and set its mount path to `/data`.
> - Under **Variables**, add:
>   - `MOONBITE_RPC_USER` = a random username (e.g. `moonrpc`)
>   - `MOONBITE_RPC_PASSWORD` = a long random password (save it — the explorer needs it)
>   - `MINE` = `1`   (so the fresh chain actually produces blocks)
> - Under **Settings → Networking**: enable a **TCP Proxy** on port **9444**
>   (this is the public P2P endpoint / seed address). Do **NOT** add a public
>   domain or proxy for port 9445.
> - Deploy. In the **Deploy Logs** confirm moonbited starts and logs
>   `MoonBite Core version`. A seed node with `MINE=0` stays at height 0 until
>   a miner elsewhere produces blocks — that is expected, not a failure.
>
> If the Volume already holds chain data from the 10 MBITE era, the entrypoint
> detects the genesis mismatch and resets it. To force a reset, set
> `RESET_CHAIN=1`, redeploy, then remove the variable.

After it's up, note two things:
- the **TCP Proxy host:port** for 9444 → this is your public **seed address**
  (use it in `addnode`/`vSeeds`).
- the private hostname **`moonbite-node.railway.internal`** → the explorer uses
  this to reach RPC 9445.

---

## Step 2 — Explorer service (Nixpacks), wired to the node

**Prompt to paste into your Railway browser session:**

> The explorer reads its RPC settings under the legacy `BIGCOIN_` prefix
> (see `explorer/config.py`); that is deliberate, not a leftover to rename.
>
> In the same Railway project, add another service from the GitHub repo
> **moonbitecoin/MoonBite-Coin**.
> - "Deploy from GitHub repo" → select `moonbitecoin/MoonBite-Coin`.
> - Name it **moonbite-explorer**.
> - In **Settings → Root Directory**, set it to `explorer` (the repo's
>   `explorer/railway.json` defines the Nixpacks build; start command is
>   `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 30`).
> - Under **Variables**, add:
>   - `BIGCOIN_RPC_HOST` = `moonbite-node.railway.internal`
>   - `BIGCOIN_RPC_PORT` = `9445`
>   - `BIGCOIN_RPC_USER` = same value set on the node
>   - `BIGCOIN_RPC_PASSWORD` = same value set on the node
>   - `BIGCOIN_NAME` = `MoonBite`
>   - `BIGCOIN_TICKER` = `MBITE`
> - Under **Settings → Networking**, generate a **public domain** for this service.
> - Deploy, then open the generated URL and confirm the home page, a block page,
>   and search all load with **real** chain data (no demo banner).

> If the node isn't producing blocks yet, the explorer will show height 0 (or a
> demo banner). Set `MINE=1` on the node and give it time; the explorer needs no
> change and will show data as blocks arrive.

---

## Files here
- `Dockerfile` — ubuntu:22.04 + moonbited runtime libs; ships `release/bin/moonbited`.
- `entrypoint.sh` — starts moonbited (P2P 9444 public, RPC 9445 private), optional `MINE=1` loop.
- `railway.json` — tells Railway to use the Dockerfile builder.
