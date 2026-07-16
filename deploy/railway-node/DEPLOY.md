# Deploy MoonBite live on Railway (node + explorer)

This directory ships the **MoonBite seed node** as a Docker service for Railway,
and pairs it with the Flask **explorer** in `explorer/`. Follow the two steps in
order — the explorer needs the node to exist first.

> **Honest launch notes — read once before deploying**
> - **A fresh chain produces NO blocks on its own.** With zero miners the height
>   stays at 0 forever. Set `MINE=1` on the node service (below) so it mines, or
>   run the miner yourself. RandomX is CPU-heavy; Railway containers are small,
>   so expect slow block production.
> - **RPC port 9445 must stay private.** Only attach a public domain / TCP proxy
>   to the **P2P port 9444**. The explorer reaches RPC over Railway's *private*
>   network (`*.railway.internal`). Never expose 9445 publicly.
> - **Persistence:** attach a Railway **Volume** mounted at `/data`, or the chain
>   is wiped on every redeploy.
> - **Binary identity:** the shipped `release/bin/moonbited` is the `big1` build.
>   It is fully network-compatible with a `moon1` build (same genesis / PoW /
>   consensus) — addresses just display with the older prefix. Cosmetic only.
> - **Railway is not the ideal home for a P2P node** (built for HTTP). A small
>   $4–6/mo VPS is more robust for a long-lived seed. This Docker path works as a
>   bootstrap seed; see `deploy/RUNBOOK.md` for the VPS route.

---

## Step 1 — Node service (Docker)

**Prompt to paste into your Railway browser session:**

> Deploy a service on Railway from the GitHub repo **zaptapagency/MoonBite**.
> - New Project → "Deploy from GitHub repo" → select `zaptapagency/MoonBite`.
> - Name the service **moonbite-node**.
> - In **Settings → Build**: set **Root Directory** to `/` (repo root) and
>   **Dockerfile Path** to `deploy/railway-node/Dockerfile`
>   (the build context must be the repo root so it can COPY `release/bin/moonbited`).
> - Add a **Volume** and set its mount path to `/data`.
> - Under **Variables**, add:
>   - `MOONBITE_RPC_USER` = a random username (e.g. `moonrpc`)
>   - `MOONBITE_RPC_PASSWORD` = a long random password (save it — the explorer needs it)
>   - `MINE` = `1`   (so the fresh chain actually produces blocks)
> - Under **Settings → Networking**: enable a **TCP Proxy** on port **9444**
>   (this is the public P2P endpoint / seed address). Do **NOT** add a public
>   domain or proxy for port 9445.
> - Deploy. In the **Deploy Logs** confirm moonbited starts and the block height
>   begins rising (`UpdateTip` / `height=` lines).

After it's up, note two things:
- the **TCP Proxy host:port** for 9444 → this is your public **seed address**
  (use it in `addnode`/`vSeeds`).
- the private hostname **`moonbite-node.railway.internal`** → the explorer uses
  this to reach RPC 9445.

---

## Step 2 — Explorer service (Nixpacks), wired to the node

**Prompt to paste into your Railway browser session:**

> In the same Railway project, add another service from the GitHub repo
> **zaptapagency/MoonBite**.
> - "Deploy from GitHub repo" → select `zaptapagency/MoonBite`.
> - Name it **moonbite-explorer**.
> - In **Settings → Root Directory**, set it to `explorer` (the repo's
>   `explorer/railway.json` defines the Nixpacks build; start command is
>   `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 30`).
> - Under **Variables**, add:
>   - `MOONBITE_RPC_HOST` = `moonbite-node.railway.internal`
>   - `MOONBITE_RPC_PORT` = `9445`
>   - `MOONBITE_RPC_USER` = same value set on the node
>   - `MOONBITE_RPC_PASSWORD` = same value set on the node
>   - `MOONBITE_NAME` = `MoonBite`
>   - `MOONBITE_TICKER` = `MBITE`
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
