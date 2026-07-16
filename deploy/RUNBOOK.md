# MoonBite Mainnet Launch Runbook

Concrete, ordered steps to take MoonBite from "runs locally" to "a public network
anyone can join." Do the phases in order. Phases 0–4 stand up the live network;
Phase 5 is what makes *end users'* clients auto-discover it; Phases 6–8 are the
supporting services and launch hygiene.

Values used throughout (from `deploy/moonbite.conf` + `explorer/config.py`):
- P2P port: **9444** (public) · RPC port: **9445** (localhost only)
- Data dir: `/var/lib/moonbite` · Config: `/etc/moonbite/moonbite.conf`
- Binaries: `release/bin/moonbited`, `moonbite-cli` (built as the Litecoin-Core fork)

---

## Phase 0 — Prerequisites (do once, before touching servers)

- [ ] **3 VPS hosts**, ideally different providers/regions (e.g. Hetzner + DigitalOcean + Vultr). 1–2 GB RAM each is enough at launch (~$5–10/mo each). Budget a 4th small host for the explorer.
- [ ] A **domain** (optional but recommended) if you want DNS seeds, e.g. `moonbite.org` with A-records `seed1/seed2/seed3.moonbite.org`.
- [ ] **Release binaries built for the target OS.** The VPS setup script installs Ubuntu 22.04 shared libs (boost 1.74, libevent, db5.3, libzmq5, libfmt8), so build the Linux binaries on an Ubuntu-22.04 toolchain to match. In WSL:
  ```bash
  wsl -d Ubuntu-22.04 -u root -e bash -lc \
    'cd /root/moonbite-core/src && make moonbited moonbite-cli 2>/dev/null; \
     cp litecoind moonbited; cp litecoin-cli moonbite-cli; \
     file moonbited'    # confirm: ELF 64-bit LSB executable
  ```
  Copy the resulting `moonbited` / `moonbite-cli` to your workstation's `release/bin/`.
- [ ] **Confirm the compiled default P2P port matches 9444.** `moonbite.conf` forces `port=9444`, but for third-party clients to connect *without* config, `nDefaultPort` for `CMainParams` in `src/chainparams.cpp` should also be `9444`. Verify/adjust before the Phase-5 rebuild.

---

## Phase 1 — Provision each seed node (repeat on all 3 VPS)

```bash
# From your workstation, per host (replace IP):
scp -r deploy release/bin/moonbited release/bin/moonbite-cli root@SEED_IP:/root/

# On the VPS:
ssh root@SEED_IP
cd /root
sudo bash deploy/setup-seednode.sh ./moonbited ./moonbite-cli
```

The script installs binaries to `/usr/local/bin`, creates the unprivileged
`moonbite` user, generates **random RPC credentials**, installs+enables the
systemd service, and opens **only** P2P 9444 in `ufw` (RPC stays on localhost).

**Record the auto-generated RPC user/pass** it prints — you'll need it for the
explorer (Phase 7). It's stored in `/etc/moonbite/moonbite.conf`.

---

## Phase 2 — Verify each node is up and reachable

```bash
systemctl status moonbited                # active (running)
journalctl -u moonbited -f                # watch startup, Ctrl-C when synced
moonbite-cli -conf=/etc/moonbite/moonbite.conf getnetworkinfo
moonbite-cli -conf=/etc/moonbite/moonbite.conf getblockchaininfo   # height should tick up
```

From **another machine**, confirm the P2P port is open to the internet:
```bash
nc -vz SEED_IP 9444        # should say "succeeded" / "open"
```
If it fails: check the provider's cloud firewall/security-group (separate from `ufw`).

Note each host's **public IP** — you need all three for the next phase.

---

## Phase 3 — Mesh the seeds together

On **every** seed, edit `/etc/moonbite/moonbite.conf` and add the *other two* IPs:
```conf
addnode=SEED_A_PUBLIC_IP
addnode=SEED_B_PUBLIC_IP
addnode=SEED_C_PUBLIC_IP
```
Then:
```bash
systemctl restart moonbited
```

## Phase 4 — Verify the mesh

```bash
moonbite-cli -conf=/etc/moonbite/moonbite.conf getpeerinfo | grep '"addr"'
moonbite-cli -conf=/etc/moonbite/moonbite.conf getconnectioncount   # >= 2
```
All three nodes should see each other and report the **same block height**. The
public network now exists — but new users still need Phase 5 to find it.

---

## Phase 5 — Bake seeds into the client (so end users auto-discover)

Without this, users must manually `addnode`. Add your seeds to `CMainParams` in
`src/chainparams.cpp`:

- **DNS seeds** (if you set up domain A-records in Phase 0):
  ```cpp
  vSeeds.emplace_back("seed1.moonbite.org");
  vSeeds.emplace_back("seed2.moonbite.org");
  vSeeds.emplace_back("seed3.moonbite.org");
  ```
- **and/or hard-coded fixed seeds** (`vFixedSeeds`) — generate from your seed IPs
  with the upstream tooling in `contrib/seeds/` (`makeseeds.py` → `generate-seeds.py`
  → `chainparamsseeds.h`).

Then rebuild and re-release. Because the in-tree binaries are named `litecoin*`,
rename after building (the known build quirk — build inside `src/` with explicit
targets, top-level `make` may skip relinking):
```bash
wsl -d Ubuntu-22.04 -u root -e bash -lc \
  'cd /root/moonbite-core/src && \
   make moonbited moonbite-cli moonbite-tx moonbite-wallet qt/moonbite-qt 2>/dev/null; \
   for b in moonbited moonbite-cli moonbite-tx moonbite-wallet; do cp litecoin${b#moonbite} $b 2>/dev/null; done'
```
Copy the fresh binaries into `release/bin/`, refresh `SHA256SUMS.txt`, and publish.
**Redeploy the new `moonbited` to the seeds too** (Phase 1) so the whole network runs
the released build.

---

## Phase 6 — (Optional) DNS seeder

Static A-records work for launch. For a self-updating seeder that crawls the
network and serves healthy peers over DNS, run `contrib/seeds`-style `bitcoin-seeder`
(fork it to MoonBite's magic bytes) on one host and point `seedN.moonbite.org` NS/A at it.
Skip this for a minimal launch — the three static seeds are enough.

---

## Phase 7 — Explorer host

On the 4th VPS (or one of the seeds, if it has spare RAM and `txindex=1`, which the
config already sets):
```bash
# Point the explorer at a local/adjacent moonbited's RPC:
export MOONBITE_RPC_HOST=127.0.0.1
export MOONBITE_RPC_PORT=9445
export MOONBITE_RPC_USER=<the generated rpcuser>
export MOONBITE_RPC_PASSWORD=<the generated rpcpassword>
export DEMO_MODE=0
cd explorer && python app.py       # serves on :5055 (put nginx + TLS in front)
```
If the explorer runs on a **different** host than moonbited, add that host's IP to
`rpcallowip=` in `moonbite.conf` and bind RPC to the private interface — **never** the
public one.

---

## Phase 8 — Launch-day checklist & maintenance

Pre-announce:
- [ ] All 3 seeds synced to identical height (`getblockchaininfo`).
- [ ] Seeds baked into the released client and binaries re-published with fresh `SHA256SUMS.txt`.
- [ ] `nc -vz` from outside confirms 9444 open on every seed; RPC 9445 **closed** externally.
- [ ] Explorer reachable over HTTPS and showing live blocks.
- [ ] Consider a **checkpoint** in `chainparams.cpp` at an early block once a few thousand blocks exist (anti-reorg for a young chain).
- [ ] Website download links point at the re-released binaries + checksums.

Ongoing (this is infrastructure you keep running **indefinitely** — if all seeds die,
new users can't find the network):
- Monitoring: alert on `systemctl is-active moonbited`, `getconnectioncount`, disk, and height-stall.
- Keep the OS patched; the systemd unit already applies `NoNewPrivileges`, `ProtectSystem`, `ProtectHome`, `PrivateTmp`.
- Seeds hold **no wallet** — a compromise can't steal coins, but patch them to protect the network.

---

### What this runbook cannot do for you
- **Coins/economics**: a live network doesn't create market value.
- **Exchange listing**: separate business/legal process — listing application, fees,
  liquidity/market-making, and often KYC/entity paperwork. No code step completes it.
